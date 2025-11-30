"""Lightweight wrapper around the external hybrid search API."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


def search_hybrid(query: str) -> Dict[str, Any]:
    """Call the hybrid search service and return parsed results."""
    base_url = os.getenv("HYBRID_SEARCH_URL", "").rstrip("/")
    token = os.getenv("HYBRID_SEARCH_TOKEN")

    if not base_url or not token:
        return {
            "error": "Hybrid search not configured. Set HYBRID_SEARCH_URL and HYBRID_SEARCH_TOKEN.",
        }

    # Allow passing either the full endpoint or just the host.
    if not base_url.endswith("/api/v1/search/hybrid"):
        endpoint = f"{base_url}/api/v1/search/hybrid"
    else:
        endpoint = base_url

    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={"query": query},
            timeout=30,
        )
        response.raise_for_status()
        payload: Dict[str, Any] = response.json()
        results: List[Dict[str, Any]] = payload.get("data", {}).get("results", [])
        return {
            "message": f"Hybrid search returned {len(results)} result(s).",
            "results": results,
        }
    except Exception as exc:  # pragma: no cover - network errors are surfaced to the agent
        return {
            "error": f"Hybrid search failed: {exc}",
        }
