"""
End-to-End Tests for the RunPlan Engine, RepoFacts Fingerprinter, and Plan Executor.
"""
import pytest
import tempfile
from pathlib import Path

from app.planner.schema import RunPlan, Service, Runtime, Readiness
from app.planner.validator import validate_plan, topo_order
from app.planner.repair import try_rules
from app.planner.facts import gather_repo_facts
from app.planner.adapters import extract_candidates_from_repo, plan_from_candidates
from app.planner.engine import resolve_and_run, ExecResult


@pytest.fixture
def temp_fullstack_repo() -> Path:
    """Creates a temporary mock full-stack repository (FastAPI backend + Vite frontend)."""
    ws = Path(tempfile.mkdtemp())
    (ws / "backend").mkdir(parents=True, exist_ok=True)
    (ws / "frontend").mkdir(parents=True, exist_ok=True)

    # Backend files
    (ws / "backend" / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (ws / "backend" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef r(): return {'status': 'ok'}\n",
        encoding="utf-8"
    )

    # Frontend files
    (ws / "frontend" / "package.json").write_text(
        '{"name": "web", "scripts": {"dev": "vite"}, "dependencies": {"react": "^18.0.0", "vite": "^5.0.0"}}',
        encoding="utf-8"
    )
    (ws / "frontend" / "index.html").write_text("<!doctype html><html><body><div id='root'></div></body></html>", encoding="utf-8")
    (ws / "README.md").write_text("# Project\n\n```bash\nuvicorn main:app\nnpm run dev\n```\n", encoding="utf-8")

    return ws


def test_repofacts_extraction(temp_fullstack_repo: Path):
    facts = gather_repo_facts(temp_fullstack_repo)
    assert "tree" in facts
    assert "manifests" in facts
    assert any("requirements.txt" in m for m in facts["manifests"])
    assert any("package.json" in m for m in facts["manifests"])
    assert "fastapi" in facts["code_imports"]
    assert any("npm run dev" in cmd for cmd in facts["readme_commands"])


def test_candidates_and_plan_generation(temp_fullstack_repo: Path):
    candidates = extract_candidates_from_repo(temp_fullstack_repo)
    assert len(candidates) >= 1
    assert candidates[0].framework in ("fastapi", "vite")
    assert candidates[0].score >= 0.8

    plan = plan_from_candidates(candidates)
    assert plan is not None
    assert plan.runnable is True
    assert plan.entry_service == "web"
    assert len(plan.services) == 2

    errors = validate_plan(plan, temp_fullstack_repo)
    assert errors == []


@pytest.mark.anyio
async def test_resolve_and_run_fast_path(temp_fullstack_repo: Path):
    facts = gather_repo_facts(temp_fullstack_repo)
    candidates = extract_candidates_from_repo(temp_fullstack_repo)

    executed_services = []

    async def mock_executor(p: RunPlan) -> ExecResult:
        for s in topo_order(p):
            executed_services.append(s.name)
        return ExecResult(ok=True, log="Mock execution succeeded")

    plan, res = await resolve_and_run(facts, candidates, str(temp_fullstack_repo), mock_executor)
    assert res.ok is True
    assert plan.runnable is True
    assert executed_services == ["api", "web"]
