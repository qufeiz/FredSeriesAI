#!/usr/bin/env python3
"""Minimal script to push FRASER statement/ROPA text files to S3."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests

# --- Edit these defaults or override via environment variables ---
SOURCE_JSON = Path(
    os.getenv(
        "FRASER_SOURCE_JSON",
        Path(__file__).parent / "output" / "title_677_items.json",
        #Path(__file__).parent / "output" / "item_23289.json",
    )
)
BUCKET = os.getenv("FRASER_S3_BUCKET", "fraser-fomc-data-for-fredgpt")
PREFIX = os.getenv("FRASER_S3_PREFIX", "fraser/fomc/")
DEFAULT_KEYWORD_MAP = {
    "statement": "statement",
    "ropa": "ropa",
    "mod": "mod",
    "moa": "moa",
    "meeting.txt": "meeting",
    "transcript.txt": "transcript",
    "min": "minutes",
}

KEYWORD_MAP = {
    key: value for key, value in DEFAULT_KEYWORD_MAP.items()
}

raw_map = os.getenv("FRASER_KEYWORD_MAP")
if raw_map:
    KEYWORD_MAP.clear()
    for part in raw_map.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, part
        KEYWORD_MAP[key.strip().lower()] = value.strip()
AWS_PROFILE = os.getenv("FRASER_AWS_PROFILE", "AWSAdministratorAccess-112393354239") or None
LIMIT = int(os.getenv("FRASER_LIMIT", "0")) or None
DRY_RUN = os.getenv("FRASER_DRY_RUN", "false").lower() in {"1", "true", "yes"}
# ----------------------------------------------------------------


def main() -> None:
    if not BUCKET or BUCKET == "my-fraser-bucket":
        raise RuntimeError("Set FRASER_S3_BUCKET (or edit BUCKET) before running.")
    if not KEYWORD_MAP:
        raise RuntimeError("Need at least one keyword to match URLs.")

    if AWS_PROFILE:
        session = boto3.session.Session(profile_name=AWS_PROFILE)
        s3 = session.client("s3")
    else:
        s3 = boto3.client("s3")

    data = json.loads(SOURCE_JSON.read_text())
    records = data.get("records", [])
    uploads = 0

    for record in records:
        record_ids = record.get("recordInfo", {}).get("recordIdentifier") or []
        if not record_ids:
            continue
        record_id = str(record_ids[0])

        for url in record.get("location", {}).get("textUrl", []):
            lowered = url.lower()
            matches = [tag for keyword, tag in KEYWORD_MAP.items() if keyword in lowered]
            if not matches:
                continue

            asset_kind = matches[0]
            filename = Path(urlparse(url).path).name or f"{record_id}_{asset_kind}.txt"
            key = f"{PREFIX.rstrip('/')}/{record_id}/{filename}"

            metadata = {
                "record-id": record_id,
                "source-url": url,
                "asset-kind": asset_kind,
            }
            title_info = (record.get("titleInfo") or [{}])[0]
            title = title_info.get("title") or ""
            if title:
                metadata["title"] = title[:500]

            if DRY_RUN:
                print(f"[DRY-RUN] {url} -> s3://{BUCKET}/{key} with metadata {metadata}")
            else:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                response.raw.decode_content = True
                s3.upload_fileobj(
                    response.raw,
                    BUCKET,
                    key,
                    ExtraArgs={
                        "ContentType": "text/plain",
                        "Metadata": metadata,
                    },
                )
                print(f"Uploaded {url} -> s3://{BUCKET}/{key}")
                print(f"Attached metadata: {metadata}")

            uploads += 1
            print(f"\rProcessed {uploads} matches so far...", end="", flush=True)
            if LIMIT and uploads >= LIMIT:
                break

        if LIMIT and uploads >= LIMIT:
            break

    print(f"\nProcessed {uploads} matches.")


if __name__ == "__main__":
    main()
