from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from retrieval_graph import fred_tool


@dataclass
class _StubClient:
    snapshot: fred_tool.SeriesSnapshot
    chart_payload: str | None = "data:image/png;base64,FAKE_IMAGE"

    def get_series_snapshot(self, series_id: str, *, limit: int = 180) -> fred_tool.SeriesSnapshot:  # noqa: D401
        return self.snapshot

    def render_chart(self, observations: list[dict[str, Any]], title: str | None, *, width: int = 6, height: int = 3) -> str | None:  # noqa: D401
        return self.chart_payload


@pytest.fixture(autouse=True)
def clear_fred_client_cache() -> None:
    """Ensure cached client does not leak between tests."""
    fred_tool.get_fred_client.cache_clear()


def _make_snapshot(count: int = 6) -> fred_tool.SeriesSnapshot:
    observations = [
        {"date": f"2024-0{month}-01", "value": float(month)}
        for month in range(1, count + 1)
    ]
    return fred_tool.SeriesSnapshot(
        series_id="TEST_SERIES",
        title="Test Series",
        units="Index",
        frequency="Monthly",
        observations=observations,
    )


def test_fetch_chart_returns_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _make_snapshot()
    stub = _StubClient(snapshot=snapshot)
    monkeypatch.setattr(fred_tool, "get_fred_client", lambda: stub)

    payload = fred_tool.fetch_chart("TEST_SERIES")

    assert "message" in payload
    attachments = payload.get("attachments")
    assert isinstance(attachments, list)
    assert attachments and attachments[0]["source"].startswith("data:image/png;base64")
    assert attachments[0]["series_id"] == "TEST_SERIES"
    assert attachments[0]["title"] == "Test Series"


def test_fetch_recent_data_respects_latest_points(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _make_snapshot(count=8)
    stub = _StubClient(snapshot=snapshot, chart_payload=None)
    monkeypatch.setattr(fred_tool, "get_fred_client", lambda: stub)

    payload = fred_tool.fetch_recent_data("TEST_SERIES", latest_points=3)

    data_blocks = payload.get("series_data")
    assert isinstance(data_blocks, list)
    assert len(data_blocks) == 1
    block = data_blocks[0]
    assert block["series_id"] == "TEST_SERIES"
    points = block["points"]
    assert len(points) == 3
    # Expect final three months in chronological order
    assert [p["date"] for p in points] == ["2024-06-01", "2024-07-01", "2024-08-01"]
