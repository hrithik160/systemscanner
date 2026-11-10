# Rules for AI Coding Agents (`AGENTS.md`)

1. **Contracts first**: Read `shared/types.ts` and `shared/models.py` before coding. Never invent endpoints, fields, or event names.
2. **Stay in your lane**:
   - **Person 1 (Local LLM & AI Agent)**: `backend/app/llm/`, `backend/app/api/routes_llm.py`
   - **Person 2 (Docker, Tests & Git Ops)**: `backend/app/runner/`, `backend/app/git_ops/`, `docker/`, `demo/`, `backend/app/api/routes_p2.py`
   - **Person 3 (Backend Core, Analysis & Risk)**: `backend/app/analysis/`, `backend/app/config.py`, `backend/app/events.py`, `backend/app/projects.py`, `shared/`, `backtest/`, `backend/app/api/routes_p3.py`
   - **Person 4 (Frontend)**: `frontend/`
3. **Deterministic first**: Graph, diff, coverage, defects, and risk numbers come from deterministic code, never from the LLM. The LLM explains, proposes, and writes.
4. **Security**: Arbitrary repo, pasted, or LLM code runs inside the Person 2 sandbox runner. Never apply an LLM patch without validation and user approval.
