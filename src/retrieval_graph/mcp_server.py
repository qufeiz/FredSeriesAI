#!/usr/bin/env python3
"""FastMCP entry point bundled for Claude Desktop extensions."""

from __future__ import annotations

from fastmcp import FastMCP

from services import get_latest_payload

app = FastMCP("fomc-decisions")


@app.tool(description="Return the latest FOMC decision with formatted card data.")
def get_latest_decision():
    return get_latest_payload()


if __name__ == "__main__":
    app.run()
