"""Unit tests for backend/app/llm/arch.py and GET /api/architecture/{pid}."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import arch, client

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_detect_architecture_happy_path(tmp_path, monkeypatch):
    """Happy path: detects FastAPI, Redis, and PostgreSQL from files and imports."""
    (tmp_path / "requirements.txt").write_text("fastapi==0.110.0\nredis>=5.0\npsycopg2-binary\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("REDIS_URL=redis://localhost:6379\n", encoding="utf-8")

    async def fake_chat(messages, schema=None, **kwargs):
        return arch._SummarySchema(
            summary="Uses FastAPI for HTTP routes. Connects to Redis for caching and PostgreSQL for persistence. Two modules directly interface with backing infrastructure."
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    nodes = [
        {"id": "redis_cache.py", "path": "redis_cache.py", "lang": "py", "deps": ["redis"]},
        {"id": "db.py", "path": "db.py", "lang": "py", "deps": ["psycopg2"]},
        {"id": "utils.py", "path": "utils.py", "lang": "py", "deps": []},
    ]
    node_codes = {
        "redis_cache.py": "import redis\nclient = redis.Redis()",
        "db.py": "import psycopg2\nconn = psycopg2.connect('')",
        "utils.py": "def helper(): return 42",
    }

    res = await arch.detect_architecture(nodes=nodes, node_codes=node_codes, project_path=tmp_path)

    assert "FastAPI" in res.stack
    assert "Redis" in res.infra
    assert "PostgreSQL" in res.infra
    linked_nodes = {lnk.node_id: lnk.infra for lnk in res.node_infra_links}
    assert linked_nodes["redis_cache.py"] == "Redis"
    assert linked_nodes["db.py"] == "PostgreSQL"
    assert "FastAPI" in res.summary


def test_architecture_endpoint_missing_project():
    """Failure path: returns 404 with structured error when project ID is unknown."""
    test_client = TestClient(app)
    resp = test_client.get("/api/architecture/unknown_pid")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"