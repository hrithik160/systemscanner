"""Unit tests asserting strict 404 and 400 error codes for missing or invalid inputs."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_summarize_missing_node_and_code_raises_404():
    """Verify that summarizing a non-existent node without providing code returns 404 NODE_NOT_FOUND."""
    response = client.post(
        "/api/node/unknown_project/missing_file.py/summarize",
        json={},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "NODE_NOT_FOUND"


def test_architecture_unknown_project_raises_404():
    """Verify that requesting architecture for an unknown project returns 404 PROJECT_NOT_FOUND."""
    response = client.get("/api/architecture/nonexistent_proj")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"


def test_testgen_missing_code_raises_404():
    """Verify that generating tests without code or a registered node returns 404 NODE_NOT_FOUND."""
    response = client.post(
        "/api/tests/generate",
        json={"pid": "proj1", "nid": "unregistered.py"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "NODE_NOT_FOUND"


def test_sandbox_connect_missing_code_raises_400():
    """Verify that sandbox connection requests without code return 400 MISSING_NODE_CODE."""
    response = client.post(
        "/api/sandbox/connect",
        json={
            "pid": "proj1",
            "source_node_id": "src.py",
            "target_node_id": "tgt.py",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "MISSING_NODE_CODE"


def test_sandbox_apply_unknown_proposal_raises_404():
    """Verify that applying an unknown or expired proposal ID returns 404 PROPOSAL_NOT_FOUND."""
    response = client.post(
        "/api/sandbox/apply",
        json={"pid": "proj1", "proposal_id": "prop_fake123"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "PROPOSAL_NOT_FOUND"


def test_agent_chat_empty_prompt_raises_400():
    """Verify that sending an empty agent prompt returns 400 INVALID_PROMPT."""
    response = client.post(
        "/api/agent/chat",
        json={"pid": "proj1", "prompt": "   "},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_PROMPT"