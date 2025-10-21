import base64
import io
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

from dotenv import load_dotenv
from fredapi import Fred
from matplotlib.figure import Figure

load_dotenv()


@dataclass(frozen=True)
class SeriesSnapshot:
    """Lightweight container for FRED series metadata and observations."""

    series_id: str
    title: str
    units: str
    frequency: str
    observations: list[dict[str, Any]]

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
        self, series_id: str, *, limit: int = 180
    ) -> SeriesSnapshot:
        """Fetch recent datapoints and metadata for a series."""
        data = self._fred.get_series(
            series_id,
            limit=limit,
            sort_order="desc",
        )
        info = self._fred.get_series_info(series_id)

        observations: list[dict[str, Any]] = []
        for date, value in zip(data.index, data.values):
            if value != value:  # filter NaNs
                continue
            if hasattr(date, "strftime"):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)
            observations.append({"date": date_str, "value": float(value)})

        # Returned in reverse chronological order; flip for charting
        observations.reverse()

        return SeriesSnapshot(
            series_id=series_id,
            title=info.get("title", series_id),
            units=info.get("units", ""),
            frequency=info.get("frequency", ""),
            observations=observations,
        )

    def render_chart(
        self,
        observations: Sequence[dict[str, Any]],
        title: str | None,
        *,
        width: int = 6,
        height: int = 3,
    ) -> str | None:
        """Render datapoints to a base64 PNG suitable for front-end display."""
        if not observations:
            return None

        figure = Figure(figsize=(width, height))
        axis = figure.subplots()

        dates = [item["date"] for item in observations]
        values = [item["value"] for item in observations]

        axis.plot(dates, values, marker="o", linewidth=2)
        axis.set_title(title or "FRED Series", fontsize=10)
        axis.set_xlabel("Date")
        axis.set_ylabel("Value")
        axis.grid(True, alpha=0.3)
        axis.tick_params(axis="x", rotation=45)

        buffer = io.BytesIO()
        figure.tight_layout()
        figure.savefig(buffer, format="png", dpi=150)
        buffer.seek(0)

        encoded = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=1)
def get_fred_client() -> FredClient:
    """Return a cached FRED client."""
    return FredClient()


def build_chart_attachment(
    snapshot: SeriesSnapshot, *, max_points: int = 90
) -> dict[str, Any]:
    """Generate a chart attachment payload for the latest datapoints."""
    client = get_fred_client()
    points = snapshot.observations[-max_points:]
    chart_image = client.render_chart(points, snapshot.title)
    if not chart_image:
        raise ValueError(f"No datapoints available to chart {snapshot.series_id}")

    return {
        "type": "image",
        "source": chart_image,
        "title": snapshot.title,
        "series_id": snapshot.series_id,
        "units": snapshot.units,
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
        "points": observations,
    }


def fetch_chart(series_id: str) -> dict[str, Any]:
    """Fetch a series and prepare an attachment-only response."""
    snapshot = get_fred_client().get_series_snapshot(series_id)
    attachment = build_chart_attachment(snapshot)
    return {
        "message": f"Generated chart for {snapshot.title} ({series_id}).",
        "attachments": [attachment],
    }


def fetch_recent_data(series_id: str, *, latest_points: int = 12) -> dict[str, Any]:
    """Fetch structured datapoints for a series."""
    snapshot = get_fred_client().get_series_snapshot(series_id)
    datablock = build_series_datablock(snapshot, latest_points=latest_points)
    return {
        "message": (
            f"Retrieved {len(datablock['points'])} recent data points for "
            f"{snapshot.title} ({series_id})."
        ),
        "series_data": [datablock],
    }
