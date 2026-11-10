"""Unit tests for backend/app/llm/testgen.py and POST /api/tests/generate."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import client, testgen

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_generate_tests_retries_once_on_runner_failure(monkeypatch):
    """Happy path + runner feedback: if first test fails in P2's runner, feeds error back once."""
    calls = []

    async def fake_chat(messages, schema=None, **kwargs):
        calls.append(messages[-1]["content"])
        if len(calls) == 1:
            return testgen.GeneratedTestResult(
                test_code="def test_broken():\n    assert 1 == 2\n",
                framework="pytest",
            )
        return testgen.GeneratedTestResult(
            test_code="def test_fixed():\n    assert 1 == 1\n",
            framework="pytest",
        )

    monkeypatch.setattr(client, "chat", fake_chat)

    async def fake_runner(pid, node_ids, test_code):
        if "1 == 2" in test_code:
            return {"passed": 0, "failed": 1, "errors": 0, "failures": [{"message": "AssertionError: 1 != 2"}]}
        return {"passed": 1, "failed": 0, "errors": 0, "failures": []}

    res = await testgen.generate_tests(
        code="def add(a, b): return a + b",
        diff="+ def add(a, b): return a + b",
        path="math_utils.py",
        project_id="demo",
        node_id="math_utils.py",
        runner_fn=fake_runner,
    )

    assert len(calls) == 2
    assert "AssertionError: 1 != 2" in calls[1]
    assert "test_fixed" in res.test_code
    assert res.framework == "pytest"


def test_generate_tests_endpoint_missing_node():
    """Failure path: returns 404 with structured error when node is missing."""
    test_client = TestClient(app)
    resp = test_client.post("/api/tests/generate", json={"pid": "proj1", "nid": "unknown.py"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NODE_NOT_FOUND"   