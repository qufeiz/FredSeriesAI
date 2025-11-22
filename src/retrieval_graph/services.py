#!/usr/bin/env python3
"""Service helpers bundled with the MCP extension."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import psycopg2


def _env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_connection():
    host = _env("PG_HOST")
    port = int(_env("PG_PORT", required=False, default="5432"))
    dbname = _env("PG_NAME")
    user = _env("PG_USER")
    password = _env("PG_PASS")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


def _coerce(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def row_to_dict(row) -> Dict[str, Any]:
    return {
        "meeting_id": row[0],
        "meeting_date": row[1].isoformat() if isinstance(row[1], date) else row[1],
        "target_range_low": _coerce(row[2]),
        "target_range_high": _coerce(row[3]),
        "ioer": _coerce(row[4]),
        "on_rrp": _coerce(row[5]),
        "repo_min_rate": _coerce(row[6]),
        "primary_credit_rate": _coerce(row[7]),
        "votes_for": row[8],
        "votes_against": row[9],
    }


def format_card(latest: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    low, high = latest["target_range_low"], latest["target_range_high"]
    headline = f"Federal funds target range: {low:.2f}%–{high:.2f}%"
    vote_line = f"Vote: {latest.get('votes_for', '')}–{latest.get('votes_against', '')}"
    tools = {
        "IOER": latest.get("ioer"),
        "ON RRP": latest.get("on_rrp"),
        "Repo min": latest.get("repo_min_rate"),
        "Primary credit": latest.get("primary_credit_rate"),
    }

    changes = None
    if previous:
        prev_low, prev_high = previous.get("target_range_low"), previous.get("target_range_high")
        if (low, high) != (prev_low, prev_high):
            changes = {
                "target_range": {
                    "previous": {"low": prev_low, "high": prev_high},
                    "current": {"low": low, "high": high},
                }
            }

    return {
        "headline": headline,
        "vote": vote_line,
        "tools": tools,
        "changes": changes,
        "meeting_id": latest.get("meeting_id"),
        "meeting_date": latest.get("meeting_date"),
    }


def fetch_latest(limit: int = 2) -> Tuple[list, Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT meeting_id, meeting_date, target_range_low, target_range_high,
                   ioer, on_rrp, repo_min_rate, primary_credit_rate,
                   votes_for, votes_against
            FROM fomc_meetings
            ORDER BY meeting_date DESC
            LIMIT %s;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    if not rows:
        raise LookupError("No meetings found")

    latest_row = row_to_dict(rows[0])
    prev_row = row_to_dict(rows[1]) if len(rows) > 1 else None
    card = format_card(latest_row, prev_row)
    return rows, latest_row, prev_row, card


def get_latest_payload() -> Dict[str, Any]:
    _, latest, prev, card = fetch_latest()
    return {"latest": latest, "previous": prev, "card": card}
