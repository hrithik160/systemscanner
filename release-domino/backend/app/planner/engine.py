"""Glue: cache -> heuristics -> Nemotron -> validate -> execute -> observe -> repair (rules first, LLM second)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from app.planner.adapters import plan_from_candidates as default_plan_from_candidates
from app.planner.planner import cache_get, cache_put, fingerprint_key, plan_with_llm, repair_with_llm
from app.planner.repair import try_rules
from app.planner.schema import RunPlan
from app.planner.validator import validate_plan

CONFIDENCE_THRESHOLD = 0.8
MAX_REPAIRS = 3


@dataclass
class ExecResult:
    ok: bool                     # preview reached (listening socket + HTTP response)
    failed_service: str = ""
    exit_code: Optional[int] = None
    log: str = ""
    reallocate_port: bool = False  # filled by the caller if needed


# Your existing runner: executes the plan (install -> build -> start DAG), returns an ExecResult.
Executor = Callable[[RunPlan], Awaitable[ExecResult]]


def plan_from_candidates(candidates: list[dict]) -> RunPlan | None:
    """Turn your adapter-registry candidates (score >= threshold) into a RunPlan. Port your detector here."""
    return default_plan_from_candidates(candidates)


async def resolve_and_run(facts: dict, candidates: list[dict], workspace: str, execute: Executor) -> tuple[RunPlan, ExecResult]:
    key = fingerprint_key(facts)
    plan = cache_get(key)
    source = "cache" if plan else ""

    if plan is None and candidates and candidates[0].get("score", 0) >= CONFIDENCE_THRESHOLD:
        plan, source = plan_from_candidates(candidates), "adapter"
    if plan is None:
        plan, source = await plan_with_llm(facts, candidates), "llm"

    last = ExecResult(ok=False, log="plan never executed")
    for attempt in range(MAX_REPAIRS + 1):
        errors = validate_plan(plan, workspace)
        if errors:
            # Treat policy violations like a failure: ask the LLM to fix the plan, never run it as-is.
            if attempt == MAX_REPAIRS:
                raise RuntimeError(f"plan rejected by policy: {errors}")
            plan = await repair_with_llm(plan, "-", None, "POLICY VIOLATIONS:\n" + "\n".join(errors))
            continue
        if not plan.runnable:
            return plan, ExecResult(ok=False, log=plan.reason or "not runnable")

        last = await execute(plan)
        if last.ok:
            if source != "cache":
                cache_put(key, plan)
            return plan, last
        if attempt == MAX_REPAIRS:
            break

        fix = try_rules(plan, last.failed_service, last.log)        # Tier 1
        last.reallocate_port = fix.reallocate_port
        if not fix.changed and not fix.needs_services:
            plan = await repair_with_llm(plan, last.failed_service, last.exit_code, last.log)  # Tier 2
        elif fix.needs_services:
            plan = await repair_with_llm(
                plan, last.failed_service, last.exit_code,
                last.log + f"\nBacking services needed: {fix.needs_services}. Substitute with SQLite/dummies.")
    return plan, last
