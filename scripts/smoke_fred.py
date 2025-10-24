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
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

# Ensure local src/ is importable when running from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_PATH = os.path.join(ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from retrieval_graph.fred_tool import (
    fetch_chart,
    fetch_recent_data,
    fetch_series_release_schedule,
    fetch_release_structure_by_name,
    search_series,
)  # noqa: E402
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
    parser.add_argument(
        "series_id",
        nargs="?",
        default="GDP",
        help="FRED series identifier (default: CPIAUCSL).",
    )
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
    parser.add_argument(
        "--out-dir",
        type=str,
        default="smoke_outputs",
        help="Directory to write chart images (default: smoke_outputs).",
    )
    parser.add_argument(
        "--release-id",
        type=int,
        default=0,
        help=(
            "Optional FRED release ID to test schedule fetch (default: 50 for GDP). "
            "Value <= 0 skips the schedule request."
        ),
    )
    parser.add_argument(
        "--release-name",
        type=str,
        default="H.4.1",
        help="Optional FRED release name (e.g. 'H.4.1') to fetch structure metadata.",
    )
    parser.add_argument(
        "--search-query",
        type=str,
        default="denmark inflation",
        help="Optional query to test the series search helper (default: inflation).",
    )
    args = parser.parse_args()

    require_env("FRED_API_KEY")

    #chart_payload = fetch_chart(args.series_id)
    #dump_section("Chart Payload", chart_payload)

    #attachments = chart_payload.get("attachments") or []
    # if attachments:
    #     output_dir = Path(args.out_dir)
    #     output_dir.mkdir(parents=True, exist_ok=True)
    #     for idx, attachment in enumerate(attachments, start=1):
    #         if attachment.get("type") != "image":
    #             continue
    #         source = attachment.get("source", "")
    #         prefix = "data:image/png;base64,"
    #         if not source.startswith(prefix):
    #             print(f"Skipping attachment {idx}: Unexpected format.")
    #             continue
    #         encoded = source[len(prefix) :]
    #         try:
    #             data = base64.b64decode(encoded)
    #         except Exception as exc:  # pragma: no cover - defensive
    #             print(f"Failed to decode attachment {idx}: {exc}")
    #             continue

    #         filename = output_dir / f"{args.series_id}_chart_{idx}.png"
    #         filename.write_bytes(data)
    #         print(f"Saved chart to {filename}")

    # data_payload = fetch_recent_data(args.series_id, latest_points=args.latest_points)
    # dump_section("Data Payload", data_payload)

    # if args.release_id > 0:
    #     schedule_payload = fetch_release_schedule(args.release_id)
    #     dump_section("Release Schedule", schedule_payload)

    series_release_payload = fetch_series_release_schedule(args.series_id)
    dump_section("Series Release Schedule", series_release_payload)

    if args.release_name:
        structure_payload = fetch_release_structure_by_name(args.release_name)
        dump_section("Release Structure", structure_payload)

    if args.search_query:
        search_payload = search_series(args.search_query)
        dump_section("Series Search", search_payload)

    if args.prompt:
        await run_agent(args.series_id, args.prompt, args.user_id)
    else:
        print("\nAgent step skipped (no prompt provided).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
