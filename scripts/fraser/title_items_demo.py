#!/usr/bin/env python3
"""Fetch FRASER title metadata, items, and a specific item."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://fraser.stlouisfed.org/api"


def require_api_key() -> str:
    api_key = os.getenv("FRASER_API_KEY")
    if not api_key:
        raise RuntimeError("Please set FRASER_API_KEY in your environment.")
    return api_key


def fetch_json(path: str, *, params: dict[str, str] | None = None) -> dict:
    response = requests.get(
        f"{BASE_URL}/{path}",
        headers={"X-API-Key": require_api_key()},
        params=params or {"format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def save_json(data: dict, filename: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(data, indent=2))
    print(f"Saved {filename} to {path.resolve()}")


def main() -> None:
    output_dir = Path(__file__).parent / "output"

    print("=== Title Metadata (ID=677) ===")
    title_meta = fetch_json("title/677", params={"format": "json"})
    save_json(title_meta, "title_677_metadata.json", output_dir)

    print("\n=== Title Items (ID=677) ===")
    title_items = fetch_json(
        "title/677/items",
        params={
            "format": "json",
            "limit": 2000,
            "fields": "titleInfo!originInfo!location!recordInfo",
        },
    )
    save_json(title_items, "title_677_items.json", output_dir)

    print("\n=== Specific Item (ID=23289) ===")
    item = fetch_json(
        "item/23289",
        params={
            "format": "json",
            "fields": "titleInfo!originInfo!location!recordInfo",
        },
    )
    save_json(item, "item_23289.json", output_dir)


if __name__ == "__main__":
    main()
