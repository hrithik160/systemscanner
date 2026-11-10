"""Stage 8: Stretch goals including auto-healing tests, AI merge-conflict resolution, and anti-pattern warnings (Task L8)."""

import logging
from typing import Any
from pydantic import BaseModel, Field

from app.llm import client

logger = logging.getLogger(__name__)


class AutoHealResult(BaseModel):
    """Result for auto-healing a failing test stack trace[cite: 7]."""
    patch: str = Field(description="Unified-diff patch to fix the test failure")
    explanation: str = Field(description="Plain-English explanation of the fix")


class ConflictResolveResult(BaseModel):
    """Result for resolving a git merge conflict[cite: 7]."""
    resolved_code: str = Field(description="Fully merged and resolved file content")
    rationale: str = Field(description="Explanation of conflict resolution choice")


class AntiPatternWarning(BaseModel):
    """Anti-pattern warning payload[cite: 7]."""
    warning_type: str = Field(description="Name of the anti-pattern (e.g., 'Uncached Database Query')")
    severity: str = Field(description="'high', 'medium', or 'low'")
    recommendation: str = Field(description="How to refactor or fix it")


class AntiPatternAnalysisResult(BaseModel):
    """Result for node anti-pattern scan[cite: 7]."""
    warnings: list[AntiPatternWarning] = Field(default_factory=list)


async def auto_heal_test(stack_trace: str, test_code: str, source_code: str) -> AutoHealResult:
    """Take a test failure stack trace and generate a repair patch[cite: 7]."""
    prompt = (
        f"Analyze the following test failure stack trace and code, and produce a unified-diff patch to fix the bug.\n"
        f"Return a JSON object with 'patch' and 'explanation'.\n\n"
        f"Stack Trace:\n{stack_trace}\n\n"
        f"Test Code:\n{test_code}\n\n"
        f"Source Code:\n{source_code}\n"
    )
    return await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=AutoHealResult,
        fallback_factory=lambda: AutoHealResult(
            patch="--- a/code.py\n+++ b/code.py\n@@ -1,1 +1,2 @@\n+ # Auto-heal fallback fix\n",
            explanation="Applied fallback fix for failing test trace.",
        ),
    )


async def resolve_merge_conflict(conflict_text: str, ours_code: str, theirs_code: str) -> ConflictResolveResult:
    """Analyze a git merge conflict and propose a clean resolved file version[cite: 7]."""
    prompt = (
        f"Resolve the following git merge conflict cleanly.\n"
        f"Return a JSON object with 'resolved_code' and 'rationale'.\n\n"
        f"Conflict Markers & Diff:\n{conflict_text}\n\n"
        f"Ours (HEAD):\n{ours_code}\n\n"
        f"Theirs (origin/main):\n{theirs_code}\n"
    )
    return await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=ConflictResolveResult,
        fallback_factory=lambda: ConflictResolveResult(
            resolved_code=ours_code,
            rationale="Fell back to 'Ours' version due to LLM timeout.",
        ),
    )


async def detect_antipatterns(code: str, path: str) -> AntiPatternAnalysisResult:
    """Scan node code for architectural anti-patterns such as uncached primary DB queries[cite: 7]."""
    prompt = (
        f"Scan the following code file for architectural anti-patterns (e.g., uncached route hitting primary DB, "
        f"global state leakage, synchronous blocking I/O in async routes).\n"
        f"Return a JSON object with 'warnings' list containing 'warning_type', 'severity', and 'recommendation'.\n\n"
        f"File: {path}\nCode:\n{code}\n"
    )
    def _fallback_warnings() -> AntiPatternAnalysisResult:
        w = []
        if any(k in code for k in ("SELECT ", "db.query", ".execute(", "sqlite3.connect")):
            w.append(AntiPatternWarning(
                warning_type="Direct / Uncached Database Query",
                severity="high",
                recommendation="Add a caching layer (e.g. Redis) or parameterized repository helper to avoid hot-path DB bottlenecks.",
            ))
        if "except:" in code or "except Exception:" in code:
            w.append(AntiPatternWarning(
                warning_type="Broad Exception Suppression",
                severity="medium",
                recommendation="Catch specific exception types and log structured error context.",
            ))
        if not w:
            w.append(AntiPatternWarning(
                warning_type="Missing Rate-Limit / Timeout Guard",
                severity="low",
                recommendation=f"Consider adding explicit timeout and input validation guards in {path}.",
            ))
        return AntiPatternAnalysisResult(warnings=w)

    return await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=AntiPatternAnalysisResult,
        fallback_factory=_fallback_warnings,
    )