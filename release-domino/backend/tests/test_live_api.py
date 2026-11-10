"""Live integration tests for Person 1's FastAPI endpoints using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.llm import client, summarize, arch, testgen, connect

client_test = TestClient(app)


def test_root_endpoint():
    """Verify the root FastAPI health-check endpoint."""
    response = client_test.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Person 1 LLM Ready" in data["service"]


@pytest.mark.asyncio
async def test_live_summarize_with_actual_code(monkeypatch):
    """Test POST /api/node/{pid}/{nid}/summarize passing an actual code snippet directly."""
    async def fake_chat(messages, schema=None, **kwargs):
        return summarize.NodeSummaryResult(
            summary=["Validates user session", "Connects to database", "Returns user profile"],
            purpose="Handles user profile fetching and validation.",
            exports=["get_user_profile"],
            risks=["SQL injection risk if unescaped"],
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    response = client_test.post(
        "/api/node/demo/profile.py/summarize",
        json={
            "code": "def get_user_profile(user_id):\n    return db.query(f'SELECT * FROM users WHERE id = {user_id}')",
            "path": "profile.py",
            "deps": ["db"],
            "lang": "py",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["summary"]) == 3
    assert data["purpose"] == "Handles user profile fetching and validation."
    assert "get_user_profile" in data["exports"]
    assert "SQL injection risk if unescaped" in data["risks"]


@pytest.mark.asyncio
async def test_live_architecture_endpoint(monkeypatch):
    """Test GET /api/architecture/{pid} using project registry."""
    async def fake_chat(messages, schema=None, **kwargs):
        return arch._SummarySchema(
            summary="This project uses FastAPI for routing and Redis for caching."
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    response = client_test.get("/api/architecture/demo")
    assert response.status_code == 200
    data = response.json()
    assert "FastAPI" in data["summary"]


@pytest.mark.asyncio
async def test_live_testgen_with_actual_code(monkeypatch):
    """Test POST /api/tests/generate passing code directly."""
    async def fake_chat(messages, schema=None, **kwargs):
        return testgen.GeneratedTestResult(
            test_code="def test_get_user_profile():\n    assert get_user_profile(1) is not None",
            framework="pytest",
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    response = client_test.post(
        "/api/tests/generate",
        json={
            "pid": "demo",
            "nid": "profile.py",
            "code": "def get_user_profile(user_id): return {'id': user_id}",
            "framework": "pytest",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "test_get_user_profile" in data["test_code"]
    assert data["framework"] == "pytest"


@pytest.mark.asyncio
async def test_live_sandbox_workflow(monkeypatch):
    """Test POST /api/sandbox/connect followed by POST /api/sandbox/apply."""
    async def fake_chat(messages, schema=None, **kwargs):
        return connect.ConnectionProposalResult(
            patch="--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,3 @@\n+ import redis\n",
            endpoint="redis.Redis()",
            rationale="Adds Redis connection import.",
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    conn_resp = client_test.post(
        "/api/sandbox/connect",
        json={
            "pid": "demo",
            "source_node_id": "redis_cache.py",
            "target_node_id": "auth.py",
            "source_code": "import redis\nclient = redis.Redis()",
            "target_code": "def authenticate(): return True",
        },
    )
    assert conn_resp.status_code == 200
    conn_data = conn_resp.json()
    proposal_id = conn_data["proposal_id"]
    assert proposal_id is not None
    assert "redis" in conn_data["patch"]

    apply_resp = client_test.post(
        "/api/sandbox/apply",
        json={"pid": "demo", "proposal_id": proposal_id},
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["status"] == "applied"