"""Unit tests for Stage 8 stretch goals (Task L8)[cite: 7]."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import client, stretch

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_auto_heal_happy_path(monkeypatch):
    """Test auto-healing test stack trace[cite: 7]."""
    async def fake_chat(messages, schema=None, **kwargs):
        return stretch.AutoHealResult(
            patch="--- a/math.py\n+++ b/math.py\n@@ -1,1 +1,2 @@\n+ # fixed division by zero\n",
            explanation="Added guard clause for zero divisor.",
        )

    monkeypatch.setattr(client, "chat", fake_chat)
    res = await stretch.auto_heal_test("ZeroDivisionError", "test_div()", "def div(a,b): return a/b")
    assert "guard clause" in res.explanation


@pytest.mark.asyncio
async def test_antipatterns_happy_path(monkeypatch):
    """Test anti-pattern detection[cite: 7]."""
    async def fake_chat(messages, schema=None, **kwargs):
        return stretch.AntiPatternAnalysisResult(
            warnings=[
                stretch.AntiPatternWarning(
                    warning_type="Uncached Database Query",
                    severity="high",
                    recommendation="Add Redis caching layer.",
                )
            ]
        )

    monkeypatch.setattr(client, "chat", fake_chat)
    res = await stretch.detect_antipatterns("db.query('SELECT * FROM users')", "users.py")
    assert len(res.warnings) == 1
    assert res.warnings[0].severity == "high"


def test_stretch_endpoints_smoke():
    """Smoke test for stretch endpoints via TestClient[cite: 7, 12]."""
    test_client = TestClient(app)
    resp = test_client.post(
        "/api/stretch/antipatterns",
        json={"code": "db.query('SELECT *')", "path": "test.py"},
    )
    assert resp.status_code == 200