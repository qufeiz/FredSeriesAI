import base64
import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import requests
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()

FRED_CHART_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.png"
DEFAULT_CHART_WIDTH = os.getenv("FRED_CHART_WIDTH", "670")
DEFAULT_CHART_HEIGHT = os.getenv("FRED_CHART_HEIGHT", "445")


@dataclass(frozen=True)
class SeriesSnapshot:
    """Lightweight container for FRED series metadata and observations."""

    series_id: str
    title: str
    units: str
    frequency: str
    observations: list[dict[str, Any]]
    notes: str | None = None

    def latest(self, count: int = 5) -> list[dict[str, Any]]:
        """Return the most recent `count` datapoints (chronological order)."""
        return self.observations[-count:]


class FredClient:
    """Thin wrapper around `fredapi.Fred` with helper formatting."""

    def __init__(self) -> None:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise RuntimeError(
                "FRED_API_KEY is required to call FRED tools but is not set."
            )
        self._fred = Fred(api_key=api_key)

    def get_series_snapshot(
        self, series_id: str, *, limit: int = 180, include_observations: bool = True
    ) -> SeriesSnapshot:
        """Fetch recent datapoints and metadata for a series."""
        info = self._fred.get_series_info(series_id)

        observations: list[dict[str, Any]] = []
        if include_observations:
            data = self._fred.get_series(
                series_id,
                limit=limit,
                sort_order="desc",
            )
            for date, value in zip(data.index, data.values):
                if value != value:  # filter NaNs
                    continue
                if hasattr(date, "strftime"):
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                observations.append({"date": date_str, "value": float(value)})
            observations.reverse()

        return SeriesSnapshot(
            series_id=series_id,
            title=info.get("title", series_id),
            units=info.get("units", ""),
            frequency=info.get("frequency", ""),
            observations=observations,
            notes=info.get("notes"),
        )

    def get_series(self, series_id: str) -> pd.Series:
        """Fetch full historical series as a pandas Series."""
        data = self._fred.get_series(series_id)
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        return data

    def get_series_metadata(self, series_id: str) -> dict[str, Any]:
        """Return metadata describing the series."""
        return self._fred.get_series_info(series_id)


@lru_cache(maxsize=1)
def get_fred_client() -> FredClient:
    """Return a cached FRED client."""
    return FredClient()


def _build_chart_url(series_id: str, *, width: str, height: str) -> str:
    params = {"id": series_id, "width": width, "height": height}
    return f"{FRED_CHART_BASE_URL}?{urlencode(params)}"


def _download_chart_image(series_id: str) -> tuple[str, bytes]:
    chart_url = _build_chart_url(
        series_id,
        width=DEFAULT_CHART_WIDTH,
        height=DEFAULT_CHART_HEIGHT,
    )
    with urlopen(chart_url) as response:  # noqa: S310 - manual script context
        data = response.read()
    return chart_url, data


def build_chart_attachment(
    snapshot: SeriesSnapshot, chart_bytes: bytes, chart_url: str
) -> dict[str, Any]:
    """Generate a chart attachment payload using FRED-rendered image bytes."""
    encoded = base64.b64encode(chart_bytes).decode("utf-8")

    return {
        "type": "image",
        "source": f"data:image/png;base64,{encoded}",
        "title": snapshot.title,
        "series_id": snapshot.series_id,
        "units": snapshot.units,
        "chart_url": chart_url,
    }


def build_series_datablock(
    snapshot: SeriesSnapshot, *, latest_points: int = 12
) -> dict[str, Any]:
    """Return structured datapoints for downstream reasoning."""
    observations = snapshot.latest(latest_points)
    return {
        "series_id": snapshot.series_id,
        "title": snapshot.title,
        "units": snapshot.units,
        "frequency": snapshot.frequency,
        "notes": snapshot.notes,
        "points": observations,
    }


def fetch_chart(series_id: str) -> dict[str, Any]:
    """Fetch a series and prepare an attachment-only response."""
    try:
        client = get_fred_client()
        snapshot = client.get_series_snapshot(series_id, include_observations=False)
        chart_url, chart_bytes = _download_chart_image(series_id)
        attachment = build_chart_attachment(snapshot, chart_bytes, chart_url)
        return {
            "message": f"Generated chart for {snapshot.title} ({series_id}).",
            "attachments": [attachment],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to generate chart for '{series_id}': {exc}",
            "attachments": [],
            "error": str(exc),
        }


def fetch_recent_data(series_id: str, *, latest_points: int = 12) -> dict[str, Any]:
    """Fetch structured datapoints for a series."""
    try:
        snapshot = get_fred_client().get_series_snapshot(series_id)
        datablock = build_series_datablock(snapshot, latest_points=latest_points)
        return {
            "message": (
                f"Retrieved {len(datablock['points'])} recent data points for "
                f"{snapshot.title} ({series_id})."
            ),
            "series_data": [datablock],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to fetch recent data for '{series_id}': {exc}",
            "series_data": [],
            "error": str(exc),
        }


def analyze_series_correlation(
    *,
    start_date: str = "1970-01-01",
    end_date: str = "1979-12-31",
    max_lag_months: int = 48,
    leading_series_id: str = "M2SL",
    lagging_series_id: str = "CPIAUCSL",
) -> dict[str, Any]:
    """Correlate YoY growth of two FRED series and inspect lead/lag behaviour."""
    try:
        client = get_fred_client()
        leading_meta = client.get_series_metadata(leading_series_id)
        lagging_meta = client.get_series_metadata(lagging_series_id)

        def _is_monthly(meta: dict[str, Any]) -> bool:
            frequency = (meta.get("frequency") or meta.get("frequency_short") or "").lower()
            return "monthly" in frequency or frequency == "m"

        if not _is_monthly(leading_meta) or not _is_monthly(lagging_meta):
            return {
                "message": (
                    "Correlation helper currently supports monthly series only. "
                    f"Leading series '{leading_series_id}' frequency: {leading_meta.get('frequency')!r}; "
                    f"Lagging series '{lagging_series_id}' frequency: {lagging_meta.get('frequency')!r}."
                ),
                "analysis": {},
                "error": "non_monthly_series",
            }

        leading = client.get_series(leading_series_id)
        lagging = client.get_series(lagging_series_id)

        leading = leading.loc[(leading.index >= start_date) & (leading.index <= end_date)]
        lagging = lagging.loc[(lagging.index >= start_date) & (lagging.index <= end_date)]

        yoy_df = pd.concat(
            {
                "leading_yoy": leading.pct_change(12) * 100,
                "lagging_yoy": lagging.pct_change(12) * 100,
            },
            axis=1,
        ).dropna()

        if yoy_df.empty:
            return {
                "message": (
                    "Insufficient overlapping data to compute year-over-year correlation "
                    f"between {leading_series_id} and {lagging_series_id} for {start_date} to {end_date}."
                ),
                "analysis": {},
            }

        yoy_corr = float(yoy_df["leading_yoy"].corr(yoy_df["lagging_yoy"]))

        lag_results: list[dict[str, float]] = []
        max_lag = max(0, int(max_lag_months))
        for lag in range(0, max_lag + 1):
            shifted = yoy_df["leading_yoy"].shift(lag)
            aligned = pd.concat(
                {"leading_yoy_shifted": shifted, "lagging_yoy": yoy_df["lagging_yoy"]},
                axis=1,
            ).dropna()
            if aligned.empty:
                continue
            corr_value = float(aligned["leading_yoy_shifted"].corr(aligned["lagging_yoy"]))
            lag_results.append({"lag_months": lag, "correlation": corr_value})

        best_positive: dict[str, float] | None = None
        worst_negative: dict[str, float] | None = None
        if lag_results:
            best_entry = max(lag_results, key=lambda item: item["correlation"])
            best_positive = {
                "lag_months": int(best_entry["lag_months"]),
                "correlation": best_entry["correlation"],
            }
            worst_entry = min(lag_results, key=lambda item: item["correlation"])
            worst_negative = {
                "lag_months": int(worst_entry["lag_months"]),
                "correlation": worst_entry["correlation"],
            }

        trend_df = pd.concat(
            {
                "log_leading": np.log(leading[leading > 0]),
                "log_lagging": np.log(lagging[lagging > 0]),
            },
            axis=1,
        ).dropna()
        log_corr = float(trend_df["log_leading"].corr(trend_df["log_lagging"])) if not trend_df.empty else None

        guidance_lines = [
            "Interpretation hints:",
            "- If both series are growth rates and the YoY correlation is negative, consider policy reactions or timing differences (e.g., central bank tightening).",
            "- A high log-level correlation with a low or opposite short-run correlation suggests strong long-run co-movement but differing cycle dynamics.",
            "- Remember that raw levels can be non-stationary; highlight possible spurious correlations if trends aren’t removed.",
            "- Avoid causal language; describe results as associations (e.g., 'tends to move with').",
        ]

        return {
            "message": (
                f"Computed correlations between {leading_series_id} (leading) and "
                f"{lagging_series_id} (lagging) from {start_date} to {end_date}."
            ),
            "analysis": {
                "window": {"start": start_date, "end": end_date},
                "series_ids": {
                    "leading": leading_series_id,
                    "lagging": lagging_series_id,
                },
                "yoy_correlation": yoy_corr,
                "best_positive_lag": best_positive,
                "most_negative_lag": worst_negative,
                "log_level_correlation": log_corr,
            },
            "analysis_guidance": "\n".join(guidance_lines),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": "Failed to compute series correlation.",
            "analysis": {},
            "error": str(exc),
        }


# def fetch_release_schedule(release_id: int) -> dict[str, Any]:
#     """Fetch scheduled release dates for a FRED release."""
#     api_key = os.getenv("FRED_API_KEY")
#     if not api_key:
#         raise RuntimeError("FRED_API_KEY is required to call release schedule tool.")

#     params: dict[str, Any] = {
#         "api_key": api_key,
#         "file_type": "json",
#         "release_id": release_id,
#         "include_release_dates_with_no_data": "true",
#     }

#     try:
#         response = requests.get(
#             "https://api.stlouisfed.org/fred/release/dates",
#             params=params,
#             timeout=10,
#         )
#         response.raise_for_status()
#         payload = response.json()
#         dates = payload.get("release_dates", [])

#         year_candidates = [
#             int(item["date"][:4])
#             for item in dates
#             if isinstance(item.get("date"), str) and item["date"][:4].isdigit()
#         ]
#         latest_year = max(year_candidates) if year_candidates else None
#         filtered_dates = [
#             item
#             for item in dates
#             if latest_year is None
#             or (
#                 isinstance(item.get("date"), str)
#                 and item["date"].startswith(str(latest_year))
#             )
#         ]

#         year_text = f" {latest_year}" if latest_year is not None else ""
#         today_str = datetime.utcnow().strftime("%Y-%m-%d")
#         return {
#             "message": (
#                 f"Retrieved {len(filtered_dates)} release dates for release {release_id}{year_text}. "
#                 f"Today: {today_str}."
#             ),
#             "release_schedule": filtered_dates,
#             "release_year": latest_year,
#         }
#     except Exception as exc:  # noqa: BLE001
#         return {
#             "message": f"Failed to fetch release schedule for '{release_id}': {exc}",
#             "release_schedule": [],
#             "error": str(exc),
#         }


def fetch_series_release_schedule(series_id: str) -> dict[str, Any]:
    """Resolve a series to its release and fetch the corresponding schedule."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY is required to call series release tool.")

    try:
        response = requests.get(
            "https://api.stlouisfed.org/fred/series/release",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        releases = data.get("releases", [])
        if not releases:
            return {
                "message": f"No release found for series '{series_id}'.",
                "release_schedule": [],
                "error": f"No release metadata for {series_id}",
            }
        release_meta = releases[0]
        release_id = int(release_meta.get("id", 0))
        release_name = release_meta.get("name", "Unknown release")

        schedule_resp = requests.get(
            "https://api.stlouisfed.org/fred/release/dates",
            params={
                "api_key": api_key,
                "file_type": "json",
                "release_id": release_id,
                "include_release_dates_with_no_data": "true",
            },
            timeout=10,
        )
        schedule_resp.raise_for_status()
        schedule_data = schedule_resp.json()
        dates = schedule_data.get("release_dates", [])

        year_candidates = [
            int(item["date"][:4])
            for item in dates
            if isinstance(item.get("date"), str) and item["date"][:4].isdigit()
        ]
        latest_year = max(year_candidates) if year_candidates else None
        filtered_dates = [
            item
            for item in dates
            if latest_year is None
            or (
                isinstance(item.get("date"), str)
                and item["date"].startswith(str(latest_year))
            )
        ]

        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        year_text = f" {latest_year}" if latest_year is not None else ""
        message = (
            f"Series {series_id} belongs to release {release_name} ({release_id}). "
            f"Retrieved {len(filtered_dates)} release dates for release {release_id}{year_text}. "
            f"Today: {today_str}."
        )
        return {
            "message": message,
            "release_schedule": filtered_dates,
            "release_year": latest_year,
            "release_info": {"id": release_id, "name": release_name},
            "series_id": series_id,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to resolve release for '{series_id}': {exc}",
            "release_schedule": [],
            "error": str(exc),
        }


def fetch_release_structure_by_name(release_name: str) -> dict[str, Any]:
    """Fetch release metadata (series count + table structure) by release name."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY is required to call release tools.")

    try:
        releases_resp = requests.get(
            "https://api.stlouisfed.org/fred/releases",
            params={
                "api_key": api_key,
                "file_type": "json",
                "limit": 1000,
            },
            timeout=10,
        )
        releases_resp.raise_for_status()
        releases_payload = releases_resp.json()
        matched_release: dict[str, Any] | None = None
        for item in releases_payload.get("releases", []):
            if release_name.lower() in item.get("name", "").lower():
                matched_release = item
                break

        if not matched_release:
            return {
                "message": f"No release found matching '{release_name}'.",
                "release": None,
                "series_metadata": None,
                "tables": None,
                "error": f"No FRED release matched '{release_name}'.",
            }

        release_id = int(matched_release.get("id", 0))
        release_title = matched_release.get("name", release_name)

        series_resp = requests.get(
            "https://api.stlouisfed.org/fred/release/series",
            params={
                "api_key": api_key,
                "file_type": "json",
                "release_id": release_id,
                "limit": 1,
            },
            timeout=10,
        )
        series_resp.raise_for_status()
        series_payload = series_resp.json()

        tables_resp = requests.get(
            "https://api.stlouisfed.org/fred/release/tables",
            params={
                "api_key": api_key,
                "file_type": "json",
                "release_id": release_id,
            },
            timeout=10,
        )
        tables_resp.raise_for_status()
        tables_payload = tables_resp.json()

        message = (
            f"Resolved release '{release_name}' to '{release_title}' "
            f"(release_id={release_id}). Retrieved series metadata and table structure."
        )
        return {
            "message": message,
            "release": matched_release,
            "series_metadata": series_payload,
            "tables": tables_payload,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to fetch release structure for '{release_name}': {exc}",
            "release": None,
            "series_metadata": None,
            "tables": None,
            "error": str(exc),
        }


def search_series(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Search for series matching a query using FRED's search API."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY is required to search FRED series.")

    try:
        response = requests.get(
            "https://api.stlouisfed.org/fred/series/search",
            params={
                "api_key": api_key,
                "file_type": "json",
                "search_text": query,
                "limit": limit,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        series = payload.get("seriess", [])
        return {
            "message": f"Found {len(series)} series for query '{query}'.",
            "results": series,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "message": f"Failed to search series for '{query}': {exc}",
            "results": [],
            "error": str(exc),
        }
