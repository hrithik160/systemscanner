"""Unit tests for backend/app/llm/summarize.py and its API endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import client, summarize

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_summarize_node_happy_path(monkeypatch):
    """Happy path: returns 3 bullets, purpose, exports, and risks."""
    async def fake_chat(messages, schema=None, **kwargs):
        return summarize.NodeSummaryResult(
            summary=["Validates user credentials", "Checks Redis session", "Issues JWT token"],
            purpose="Handles user authentication and token generation.",
            exports=["login", "verify_token"],
            risks=["Missing rate limit on login attempts"],
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    res = await summarize.summarize_node(
        code="def login(user, pw): return True",
        path="auth.py",
        deps=["redis_cache", "db"],
    )

    assert len(res.summary) == 3
    assert res.purpose == "Handles user authentication and token generation."
    assert "login" in res.exports
    assert len(res.risks) == 1


@pytest.mark.asyncio
async def test_prewarm_emits_summary_ready(monkeypatch):
    """Pre-warm summarizes only crown jewels and changed nodes and emits summary_ready."""
    async def fake_chat(messages, schema=None, **kwargs):
        return summarize.NodeSummaryResult(
            summary=["Bullet 1", "Bullet 2", "Bullet 3"],
            purpose="Core auth module.",
            exports=["authenticate"],
            risks=["High defect history"],
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    events = []
    async def record_event(evt):
        events.append(evt)

    nodes = [
        {"id": "auth.py", "path": "auth.py", "is_crown_jewel": True, "status": "normal"},
        {"id": "utils.py", "path": "utils.py", "is_crown_jewel": False, "status": "normal"},
    ]

    results = await summarize.prewarm_summaries(
        project_id="demo",
        nodes=nodes,
        get_node_code=lambda nid: "def authenticate(): pass",
        emit_event=record_event,
    )

    # Only auth.py should be pre-warmed, not utils.py
    assert "auth.py" in results
    assert "utils.py" not in results
    assert len(events) == 1
    assert events[0]["type"] == "summary_ready"
    assert events[0]["payload"]["node_id"] == "auth.py"


def test_summarize_endpoint_failure_missing_node():
    """Failure path: returns 404 with structured error when node code is missing."""
    test_client = TestClient(app)
    resp = test_client.post("/api/node/proj1/missing_node/summarize")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NODE_NOT_FOUND"