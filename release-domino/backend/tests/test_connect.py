"""Unit tests for backend/app/llm/connect.py and sandbox endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import client, connect

app = FastAPI()
app.include_router(router)


@pytest.mark.anyio
async def test_propose_connection_happy_path(monkeypatch):
    """Happy path: proposes patch, endpoint, and rationale with valid Python syntax."""
    async def fake_chat(messages, schema=None, **kwargs):
        return connect.ConnectionProposalResult(
            patch="--- a/login.py\n+++ b/login.py\n@@ -1,2 +1,3 @@\n+ from rate_limiter import check_limit\n  def login(): pass",
            endpoint="check_limit()",
            rationale="Adds rate limiting middleware call inside login function.",
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    res = await connect.propose_connection(
        src_code="def check_limit(): return True",
        dst_code="def login(): pass",
        src_path="rate_limiter.py",
        dst_path="login.py",
        lang="py",
    )

    assert "rate_limiter" in res.patch
    assert res.endpoint == "check_limit()"
    assert "rate limiting" in res.rationale


def test_sandbox_apply_endpoint_missing_proposal():
    """Failure path: returns 404 with structured error when proposal ID is unknown."""
    test_client = TestClient(app)
    resp = test_client.post("/api/sandbox/apply", json={"pid": "proj1", "proposal_id": "bad_id"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "PROPOSAL_NOT_FOUND"