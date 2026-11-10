"""Unit tests for backend/app/llm/agent.py and POST /api/agent/chat."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_llm import router
from app.llm import agent, client

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_agent_loop_happy_path(monkeypatch):
    """Happy path: agent executes tools and concludes with a patch."""
    responses = [
        agent.AgentStepResponse(thought="Reading node code", tool="read_node", tool_arg="auth.py"),
        agent.AgentStepResponse(
            thought="Drafting rate limiter patch",
            tool="done",
            tool_arg="",
            patch_result="--- a/auth.py\n+++ b/auth.py\n@@ -1,1 +1,2 %>\n+ import redis_rate_limiter\n",
        ),
    ]
    call_count = {"idx": 0}

    async def fake_chat(messages, schema=None, **kwargs):
        resp = responses[min(call_count["idx"], len(responses) - 1)]
        call_count["idx"] += 1
        return resp

    monkeypatch.setattr(client, "chat", fake_chat)

    res = await agent.run_agent_loop(
        project_id="demo",
        prompt="Add a Redis rate limiter to auth",
        get_node_code=lambda pid, nid: "def auth(): pass",
    )

    assert len(res.steps) >= 1
    assert "auth.py" in res.patch