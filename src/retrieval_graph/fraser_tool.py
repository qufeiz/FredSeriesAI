"""Helpers for querying FRASER-derived data (e.g., Postgres FOMC index)."""

from __future__ import annotations

import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def _pg_connect():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        dbname=os.getenv("PG_NAME"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
    )


def search_fomc_titles(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Run a fuzzy title search against the indexed FOMC items."""
    if not query:
        return {
            "message": "No query provided for FRASER title search.",
            "results": [],
            "error": "missing_query",
        }

    try:
        with _pg_connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    titleInfo->0->>'title' AS title,
                    location
                FROM fomc_items
                ORDER BY similarity(titleInfo->0->>'title', %s) DESC
                LIMIT %s
                """,
                (query, limit),
            )
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to search FOMC titles for '{query}'.",
            "results": [],
            "error": str(exc),
        }

    results: list[dict[str, Any]] = []
    for row in rows:
        location = row.get("location") or {}
        pdf_urls = location.get("pdfUrl") or []
        results.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "pdf_urls": pdf_urls,
            }
        )

    return {
        "message": f"Found {len(results)} titles similar to '{query}'.",
        "results": results,
    }
