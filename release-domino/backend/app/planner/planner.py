"""Nemotron-backed planner. Talks to NVIDIA's OpenAI-compatible endpoint (build.nvidia.com or a self-hosted NIM)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import ValidationError

try:
    from app.planner.schema import RunPlan
except ImportError:
    from schema import RunPlan

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# Check build.nvidia.com / GET /v1/models for the current id; override via env without a code change.
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b")
CACHE_DIR = Path(os.getenv("RD_PLAN_CACHE", Path.home() / ".cache" / "rd_plans"))
MAX_FACTS_CHARS = 24_000

client = AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=os.getenv("NVIDIA_API_KEY", "missing"))

PLANNER_SYSTEM = """You are the planning component of a sandbox that runs arbitrary GitHub repositories.
Given facts about a repository, output ONE JSON RunPlan that starts it so a web preview is reachable.

Rules:
1. Prefer commands that appear in the README, Procfile, Dockerfile CMD, docker-compose, Makefile or package scripts.
   Only invent a command when none exists, and then use the framework's standard dev-server command.
2. Never hardcode ports or hosts. Use the placeholders {HOST}, {PORT} and {services.<name>.url}.
   Pass them through the framework's CLI flag or env var (PORT, --port, --server.port, --urls ...).
3. Commands are argv arrays, e.g. ["npm","run","dev","--","--host","{HOST}","--port","{PORT}"].
   No shell syntax: no &&, ||, |, ;, $(), redirects, or env prefixes. Use the `env` map for variables.
4. Use only these binaries: python, pip, uv, pytest, gunicorn, uvicorn, node, npm, npx, pnpm, yarn, bun, go, cargo,
   java, mvn, gradle, php, composer, ruby, bundle, rails, dotnet, make, or project-local ./mvnw ./gradlew bin/rails.
5. Replace external services with sandbox-safe substitutes: SQLite for DATABASE_URL, dummy values for secrets and
   API keys. Never use real credentials. Do not invent values for paths on the host.
6. Frontend + backend: give the frontend `depends_on` the backend and set its API base URL env var
   (VITE_API_URL, NEXT_PUBLIC_API_URL, REACT_APP_API_URL) to {services.<backend>.url}. entry_service is the frontend.
7. Expo / React Native without a web target, libraries, CLIs and notebooks are not previewable:
   return runnable=false with a one-sentence reason (or runnable=true for only the web services in a monorepo and
   say what you skipped in `notes`).
8. Install commands run with network, start commands run without. Put everything that downloads in install/build.
9. confidence is your honest 0..1 estimate that this plan starts cleanly on the first try.
Output only the JSON object."""

REPAIR_SYSTEM = PLANNER_SYSTEM + """

You are now repairing a plan that failed. You receive the previous plan, the failing service, its exit code and the
last log lines. Return a corrected full RunPlan. Change the minimum needed. Fix the plan (commands, env, versions,
install steps); never propose editing the repository's source code."""


def _extract_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return text[start : end + 1]


async def _ask(system: str, user: str, retries: int = 2) -> RunPlan:
    schema = RunPlan.model_json_schema()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err = ""
    for _ in range(retries + 1):
        resp = await client.chat.completions.create(
            model=NEMOTRON_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_schema", "json_schema": {"name": "RunPlan", "schema": schema}},
            # Reasoning off: planning is a short structured task and thinking tokens only add latency.
            # Parameter name varies by Nemotron generation; remove if your endpoint rejects it.
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        raw = resp.choices[0].message.content or ""
        try:
            return RunPlan.model_validate_json(_extract_json(raw))
        except (ValueError, ValidationError) as e:
            last_err = str(e)[:1500]
            messages += [
                {"role": "assistant", "content": raw[:4000]},
                {"role": "user", "content": f"That was invalid: {last_err}\nReturn a corrected JSON object only."},
            ]
    raise RuntimeError(f"planner failed schema validation after retries: {last_err}")


def fingerprint_key(facts: dict) -> str:
    """Cache key: manifests + tree, so unrelated edits (source changes) still hit the cache."""
    blob = json.dumps({"tree": facts.get("tree"), "manifests": facts.get("manifests")}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def cache_get(key: str) -> RunPlan | None:
    p = CACHE_DIR / f"{key}.json"
    try:
        return RunPlan.model_validate_json(p.read_text())
    except (OSError, ValidationError):
        return None


def cache_put(key: str, plan: RunPlan) -> None:
    """Call only after the plan reached a live preview."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(plan.model_dump_json(indent=2))


async def plan_with_llm(facts: dict, candidates: list[dict]) -> RunPlan:
    user = json.dumps({"repo_facts": facts, "heuristic_candidates": candidates}, default=str)[:MAX_FACTS_CHARS]
    return await _ask(PLANNER_SYSTEM, user)


async def repair_with_llm(plan: RunPlan, failed_service: str, exit_code: int | None, log: str) -> RunPlan:
    user = json.dumps({
        "previous_plan": plan.model_dump(),
        "failed_service": failed_service,
        "exit_code": exit_code,
        "last_log_lines": "\n".join(log.splitlines()[-80:])[-8000:],
    })
    return await _ask(REPAIR_SYSTEM, user)
