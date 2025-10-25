#!/usr/bin/env python3
"""Simple FRASER title search demo."""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def require_api_key() -> str:
    api_key = os.getenv("FRASER_API_KEY")
    if not api_key:
        raise RuntimeError("Please set FRASER_API_KEY in your environment.")
    return api_key


def fraser_search_title(query: str, *, limit: int = 10) -> None:
    url = "https://fraser.stlouisfed.org/api/title"
    headers = {"X-API-Key": require_api_key()}
    params = {
        "format": "json",
        "fields": "titleInfo,recordInfo",
        "limit": limit,
        "page": 1,
        "search": query,
    }

    print(f"\n🔎 Searching FRASER for: {query}")
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    records = data.get("records", [])
    if not records:
        print("No titles found.")
        return

    for record in records:
        title = record.get("titleInfo", [{}])[0].get("title", "Unknown title")
        rec_id = record.get("recordInfo", {}).get("recordIdentifier", ["Unknown ID"])[0]
        print(f"- {rec_id}: {title}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "FOMC January 2010"
    fraser_search_title(query)
