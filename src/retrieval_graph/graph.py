"""Main entrypoint for the conversational retrieval graph."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable

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
    search_series,
)
from retrieval_graph.state import InputState, State
from retrieval_graph.utils import format_docs, load_chat_model

from langsmith import Client

print("API key:", os.getenv("LANGSMITH_API_KEY"))
print("Project:", os.getenv("LANGSMITH_PROJECT"))

client = Client()
print("Projects:", [p.name for p in client.list_projects()])

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
    model = load_chat_model(configuration.response_model).bind_tools(TOOL_DEFINITIONS)

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

    last_message = state.messages[-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []

    for tool_call in tool_calls:
        name = tool_call.get("name")
        args = tool_call.get("args") or {}
        call_id = tool_call.get("id")

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
        else:
            content = f"Tool '{name}' is not implemented."

        tool_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=call_id or "",
            )
        )

    updates: dict[str, Any] = {"messages": tool_messages}
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
