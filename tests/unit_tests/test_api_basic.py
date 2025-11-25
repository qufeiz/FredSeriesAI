import os
import sys

from fastapi.testclient import TestClient

TESTS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import api_server as api  # type: ignore

client = TestClient(api.app)


def test_healthcheck() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "healthy"


def test_ask_stubbed_graph(monkeypatch) -> None:
    class DummyMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    async def fake_graph(payload, config):  # type: ignore[override]
        return {
            "messages": [DummyMessage("stubbed response")],
            "attachments": [],
            "series_data": [],
            "sources": [],
            "tool_call_count": 0,
        }

    monkeypatch.setattr(api.graph, "ainvoke", fake_graph)

    resp = client.post(
        "/ask",
        json={"text": "hi", "conversation": []},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("response") == "stubbed response"
    assert body.get("tool_call_count") == 0
