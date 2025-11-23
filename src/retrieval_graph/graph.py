"""Main entrypoint for the conversational retrieval graph."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable

import boto3
from langchain_aws import ChatBedrockConverse
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from retrieval_graph import retrieval
from retrieval_graph.configuration import Configuration
from retrieval_graph.fred_tool import (
    fetch_chart,
    fetch_recent_data,
    fetch_series_release_schedule,
    fetch_release_structure_by_name,
    analyze_series_correlation,
    search_series,
)
from retrieval_graph.fraser_tool import search_fomc_titles
from retrieval_graph.services import get_latest_payload
from retrieval_graph.state import InputState, State
from retrieval_graph.utils import format_docs

# from langsmith import Client

# print("API key:", os.getenv("LANGSMITH_API_KEY"))
# print("Project:", os.getenv("LANGSMITH_PROJECT"))

# client = Client()
# print("Projects:", [p.name for p in client.list_projects()])

MAX_TOOL_CALLS = 20

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_documents",
            "description": (
                "Use this tool to search the indexed knowledge base for information "
                "relevant to the user's question. Provide a concise natural language query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to retrieve supporting documents.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_chart",
            "description": (
                "Render a chart for a FRED series and share the image with the user. "
                "Call this when the user asks for a plot or visualization."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "series_id": {
                        "type": "string",
                        "description": "Exact FRED series identifier (e.g. CPIAUCSL).",
                    }
                },
                "required": ["series_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_recent_data",
            "description": (
                "Fetch recent numeric datapoints for a FRED series and use them in analysis. "
                "Call this when the user needs the latest figures or trends."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "series_id": {
                        "type": "string",
                        "description": "Exact FRED series identifier (e.g. UNRATE).",
                    }
                },
                "required": ["series_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_series_release_schedule",
            "description": (
                "Resolve a FRED series to its release and return upcoming release dates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "series_id": {
                        "type": "string",
                        "description": "FRED series identifier (e.g. UNRATE, CPIAUCSL).",
                    }
                },
                "required": ["series_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_release_structure",
            "description": (
                "Fetch release metadata and table structure by release name (e.g. H.4.1)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "release_name": {
                        "type": "string",
                        "description": "FRED release name to inspect (e.g. H.4.1).",
                    }
                },
                "required": ["release_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fraser_search_fomc_titles",
            "description": (
                "Search the FRASER/Postgres FOMC catalog for meeting titles (e.g. 'Meeting, January 2010')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Fuzzy title query, e.g. 'Meeting, January 26-27, 2010'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_search_series",
            "description": "Search the FRED catalog for series matching a text query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search text to find FRED series.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fred_series_correlation",
            "description": (
                "Analyze how two FRED series move together by comparing YoY changes and lead/lag behavior."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "leading_series_id": {
                        "type": "string",
                        "description": "Series assumed to lead (default: M2SL).",
                    },
                    "lagging_series_id": {
                        "type": "string",
                        "description": "Series assumed to lag (default: CPIAUCSL).",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for the analysis window (YYYY-MM-DD, default: 1970-01-01).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for the analysis window (YYYY-MM-DD, default: 1979-12-31).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fomc_latest_decision",
            "description": "Fetch the latest FOMC decision card (target range, vote, tools).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _summarize_documents(docs: Iterable[Document], *, max_docs: int = 3) -> str:
    """Convert retrieved docs into a compact string for tool feedback."""
    limited = list(docs)[:max_docs]
    if not limited:
        return "No documents were retrieved."
    return format_docs(limited)


async def call_model(
    state: State, *, config: RunnableConfig
) -> dict[str, Any]:
    """Ask the model what to do next (answer or call tools)."""
    configuration = Configuration.from_runnable_config(config)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", configuration.response_system_prompt),
            ("placeholder", "{messages}"),
        ]
    )
    # model = load_chat_model(configuration.response_model).bind_tools(TOOL_DEFINITIONS)
    profile_name = os.environ.get("AWS_PROFILE")
    if profile_name:
        session = boto3.Session(profile_name=profile_name)
    else:
        session = boto3.Session()
    bedrock_client = session.client("bedrock-runtime", region_name="us-east-1")
    
    model = ChatBedrockConverse(
        client=bedrock_client,
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        #model="meta.llama3-1-70b-instruct-v1:0",
        temperature=0,
    ).bind_tools(TOOL_DEFINITIONS)

    retrieved_docs = format_docs(state.retrieved_docs)
    message_value = await prompt.ainvoke(
        {
            "messages": state.messages,
            "retrieved_docs": retrieved_docs,
            "system_time": datetime.now(tz=timezone.utc).isoformat(),
        },
        config,
    )
    response = await model.ainvoke(message_value, config)
    return {"messages": [response]}


async def call_tool(
    state: State, *, config: RunnableConfig
) -> dict[str, Any]:
    """Execute tool calls emitted by the model."""
    if not state.messages:
        return {}

    attachments: list[dict[str, Any]] = []
    series_data: list[dict[str, Any]] = []
    collected_docs: list[Document] = []
    collected_queries: list[str] = []
    tool_messages: list[ToolMessage] = []
    tool_call_count = int(getattr(state, "tool_call_count", 0) or 0)
    sources: list[dict[str, Any]] = []

    last_message = state.messages[-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []

    for tool_call in tool_calls:
        name = tool_call.get("name")
        args = tool_call.get("args") or {}
        call_id = tool_call.get("id")

        source_record: dict[str, Any] | None = None

        if tool_call_count >= MAX_TOOL_CALLS:
            content = (
                "Tool-call limit reached. Provide the best answer you can with the "
                "information already collected."
            )
            tool_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=call_id or "",
                )
            )
            break

        if name == "retrieve_documents":
            query = args.get("query")
            if not query:
                content = "No query provided to retrieval tool."
            else:
                with retrieval.make_retriever(config) as retriever:
                    docs = await retriever.ainvoke(query, config)
                collected_docs.extend(docs)
                collected_queries.append(query)
                content = _summarize_documents(docs)
        elif name == "fred_chart":
            series_id = args.get("series_id")
            if not series_id:
                content = "A FRED series_id is required for chart generation."
            else:
                payload = fetch_chart(series_id)
                attachments.extend(payload.get("attachments", []))
                content = payload.get("message", f"Chart generated for {series_id}.")
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "series_id": series_id,
                    "attachments": payload.get("attachments", []),
                }
        elif name == "fred_recent_data":
            series_id = args.get("series_id")
            if not series_id:
                content = "A FRED series_id is required to fetch recent data."
            else:
                payload = fetch_recent_data(series_id)
                series_blocks = payload.get("series_data", [])
                series_data.extend(series_blocks)
                block_json = json.dumps(series_blocks, indent=2)
                content = f"{payload.get('message', 'Retrieved series data.')}\n{block_json}"
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "series_id": series_id,
                    "series_data": series_blocks,
                }
        # elif name == "fred_release_schedule":
        #     release_id = args.get("release_id")
        #     if release_id in (None, ""):
        #         content = "A FRED release_id is required to fetch the release schedule."
        #     else:
        #         release_id_int = int(release_id)
        #         payload = fetch_release_schedule(release_id_int)
        #         schedule = payload.get("release_schedule", [])
        #         message = payload.get(
        #             "message",
        #             f"Retrieved release schedule for {release_id_int}.",
        #         )
        #         content_lines = [message]
        #         if schedule:
        #             content_lines.append(json.dumps(schedule, indent=2))
        #         elif payload.get("error"):
        #             content_lines.append(f"Error: {payload['error']}")
        #         else:
        #             content_lines.append("No release dates returned.")
        #         content = "\n".join(content_lines)
        elif name == "fred_series_release_schedule":
            series_id = args.get("series_id")
            if not series_id:
                content = (
                    "A FRED series_id is required to fetch the series release schedule."
                )
            else:
                payload = fetch_series_release_schedule(series_id)
                schedule = payload.get("release_schedule", [])
                message = payload.get(
                    "message",
                    f"Retrieved release schedule for {series_id}.",
                )
                lines = [message]
                if schedule:
                    lines.append(json.dumps(schedule, indent=2))
                elif payload.get("error"):
                    lines.append(f"Error: {payload['error']}")
                else:
                    lines.append("No release dates returned.")
                content = "\n".join(lines)
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "series_id": series_id,
                    "release_schedule": schedule,
                }
        elif name == "fred_release_structure":
            release_name = args.get("release_name")
            if not release_name:
                content = (
                    "A release_name is required to fetch release structure metadata."
                )
            else:
                payload = fetch_release_structure_by_name(release_name)
                message = payload.get(
                    "message",
                    f"Retrieved release structure for {release_name}.",
                )
                content = f"{message}\n{json.dumps(payload, indent=2)}"
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "release_name": release_name,
                    "data": payload,
                }
        elif name == "fred_search_series":
            query = args.get("query")
            if not query:
                content = "A search query is required to search FRED series."
            else:
                payload = search_series(query)
                message = payload.get(
                    "message",
                    f"Retrieved search results for '{query}'.",
                )
                content = f"{message}\n{json.dumps(payload, indent=2)}"
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "query": query,
                    "results": payload.get("results", []),
                }
        elif name == "fred_series_correlation":
            leading_series_id = args.get("leading_series_id", "M2SL")
            lagging_series_id = args.get("lagging_series_id", "CPIAUCSL")
            start_date = args.get("start_date", "1970-01-01")
            end_date = args.get("end_date", "1979-12-31")
            payload = analyze_series_correlation(
                leading_series_id=leading_series_id,
                lagging_series_id=lagging_series_id,
                start_date=start_date,
                end_date=end_date,
            )
            analysis = payload.get("analysis", {})
            guidance = payload.get("analysis_guidance")

            content_parts = [payload.get("message", "Correlation analysis completed.")]
            if analysis:
                content_parts.append(json.dumps(analysis, indent=2))
            if guidance:
                content_parts.append(guidance)
            content = "\n\n".join(content_parts)
            tool_call_count += 1
            source_record = {
                "tool": name,
                "leading_series_id": leading_series_id,
                "lagging_series_id": lagging_series_id,
                "window": analysis.get("window"),
                "results": analysis,
                "guidance": guidance,
            }
        elif name == "fraser_search_fomc_titles":
            query = args.get("query")
            if not query:
                content = "A query is required to search FOMC titles."
            else:
                payload = search_fomc_titles(query)
                message = payload.get(
                    "message",
                    f"Retrieved FOMC titles for '{query}'.",
                )
                content = f"{message}\n{json.dumps(payload, indent=2)}"
                tool_call_count += 1
                source_record = {
                    "tool": name,
                    "query": query,
                    "results": payload.get("results", []),
                }
        elif name == "fomc_latest_decision":
            payload = get_latest_payload()
            message = "Fetched latest FOMC decision card."
            content = f"{message}\n{json.dumps(payload, indent=2)}"
            tool_call_count += 1
            source_record = {
                "tool": name,
                "card": payload.get("card"),
                "latest": payload.get("latest"),
                "previous": payload.get("previous"),
            }
        else:
            content = f"Tool '{name}' is not implemented."

        tool_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=call_id or "",
            )
        )
        if source_record:
            sources.append(source_record)

    updates: dict[str, Any] = {
        "messages": tool_messages,
        "tool_call_count": tool_call_count,
        "sources": sources,
    }
    if attachments:
        updates["attachments"] = attachments
    if series_data:
        updates["series_data"] = series_data
    if collected_docs:
        updates["retrieved_docs"] = collected_docs
    if collected_queries:
        updates["queries"] = collected_queries
    return updates


def should_continue(state: State) -> str:
    """Route based on whether the last AI message requested tool usage."""
    if not state.messages:
        return "__end__"

    last = state.messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "__end__"


builder = StateGraph(State, input=InputState, config_schema=Configuration)
builder.add_node("agent", call_model)
builder.add_node("tools", call_tool)

builder.add_edge("__start__", "agent")
builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "__end__": "__end__",
    },
)
builder.add_edge("tools", "agent")

graph = builder.compile(
    interrupt_before=[],
    interrupt_after=[],
)
graph.name = "RetrievalGraph"
