"""Unit tests for backend/app/llm/client.py using a mocked server."""

import json
import pytest
import httpx
from pydantic import BaseModel

from app.llm import client


class DummySchema(BaseModel):
    purpose: str
    count: int


@pytest.mark.asyncio
async def test_chat_happy_path(tmp_path, monkeypatch):
    """Happy path: valid JSON returned from server, validated via Pydantic, and cached."""
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)

    async def mock_post(self, url, json=None, **kwargs):
        # Verify secrets were stripped before leaving client
        sent_text = json["messages"][-1]["content"]
        assert "super_secret_123" not in sent_text
        return httpx.Response(
            200,
            json={"message": {"content": '{"purpose": "Handles login", "count": 3}'}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await client.chat(
        messages=[{"role": "user", "content": "API_KEY=super_secret_123\ndef login(): pass"}],
        schema=DummySchema,
    )

    assert isinstance(result, DummySchema)
    assert result.purpose == "Handles login"
    assert result.count == 3


@pytest.mark.asyncio
async def test_chat_failure_uses_fallback(tmp_path, monkeypatch):
    """Failure path: server returns invalid JSON across retries, triggering deterministic fallback."""
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)
    calls = {"count": 0}

    async def mock_failing_post(self, url, json=None, **kwargs):
        calls["count"] += 1
        return httpx.Response(
            200,
            json={"message": {"content": "NOT_VALID_JSON"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_failing_post)

    result = await client.chat(
        messages=[{"role": "user", "content": "Explain code"}],
        schema=DummySchema,
        fallback_factory=lambda: DummySchema(purpose="Fallback summary", count=0),
    )

    # Should have tried 1 initial + 2 retries = 3 calls total
    assert calls["count"] == 3
    assert result.purpose == "Fallback summary"