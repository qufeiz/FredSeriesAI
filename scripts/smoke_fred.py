#!/usr/bin/env python3
"""Manual smoke test for live FRED + agent interactions.

Usage:
    python scripts/smoke_fred.py CPIAUCSL --prompt "Show me the latest CPI value"

The script:
1. Calls the FRED chart and data helpers to ensure live responses.
2. Optionally runs the conversational graph with a single user message.

Intended for manual checks only (not part of automated CI).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from langchain_core.messages import HumanMessage

# Ensure local src/ is importable when running from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from retrieval_graph.fred_tool import fetch_chart, fetch_recent_data  # noqa: E402
from retrieval_graph.graph import graph  # noqa: E402


def require_env(var: str) -> None:
    """Fail fast if an expected environment variable is missing."""
    if not os.getenv(var):
        raise RuntimeError(f"{var} is required for this smoke test but is not set.")


def dump_section(title: str, payload: Any) -> None:
    """Pretty-print a section header and JSON payload."""
    print(f"\n=== {title} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2))
    else:
        print(payload)


async def run_agent(series_id: str, prompt: str, user_id: str) -> None:
    """Invoke the retrieval graph with a single message."""
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        {"configurable": {"user_id": user_id}},
    )
    dump_section("Agent Response", [m.content for m in result.get("messages", [])])
    if attachments := result.get("attachments"):
        dump_section("Attachments", attachments)
    if series_data := result.get("series_data"):
        dump_section("Series Data", series_data)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("series_id", help="FRED series identifier (e.g. CPIAUCSL)")
    parser.add_argument(
        "--latest-points",
        type=int,
        default=6,
        help="Number of recent datapoints to fetch for verification (default: 6)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="",
        help="Optional user message to send through the agent.",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="smoke-user",
        help="User id to pass through the graph (default: smoke-user).",
    )
    args = parser.parse_args()

    require_env("FRED_API_KEY")

    chart_payload = fetch_chart(args.series_id)
    dump_section("Chart Payload", chart_payload)

    data_payload = fetch_recent_data(args.series_id, latest_points=args.latest_points)
    dump_section("Data Payload", data_payload)

    if args.prompt:
        await run_agent(args.series_id, args.prompt, args.user_id)
    else:
        print("\nAgent step skipped (no prompt provided).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
