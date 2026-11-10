"""Node code summarization and background pre-warming (Task L3)."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field
try:
    from pydantic import field_validator
except ImportError:
    from pydantic import validator as field_validator

from app.llm import client
from app.llm.prompts import SUMMARIZE_NODE_PROMPT

logger = logging.getLogger(__name__)

# ~6k tokens is roughly 24,000 characters
MAX_CODE_CHARS = 24000


class NodeSummaryResult(BaseModel):
    """Validated output shape for node summaries."""
    summary: list[str] = Field(description="Exactly 3 plain-English bullet strings")
    purpose: str = Field(description="1-sentence purpose of the file")
    exports: list[str] = Field(default_factory=list, description="Exported functions, classes, or routes")
    risks: list[str] = Field(default_factory=list, description="Potential failure modes or risks")

    @field_validator("summary")
    @classmethod
    def ensure_three_bullets(cls, v: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in v if str(item).strip()]
        while len(cleaned) < 3:
            cleaned.append("Contains application logic and module dependencies.")
        return cleaned[:3]


def _detect_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "py",
        ".ts": "ts",
        ".tsx": "ts",
        ".js": "js",
        ".jsx": "js",
    }.get(ext, "other")


def trim_code(code: str, max_chars: int = MAX_CODE_CHARS) -> str:
    """Trim source code to roughly 6k tokens so the local model stays fast."""
    if len(code) <= max_chars:
        return code
    return code[:max_chars] + "\n# ... [truncated to 6k tokens]"


def _build_fallback_summary(code: str, path: str, deps: list[str]) -> NodeSummaryResult:
    """Deterministic AST/regex fallback summary if the local LLM is offline or times out."""
    import re
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    loc = len(lines)
    exports = re.findall(r"(?:^|\n)\s*(?:async\s+def|def|class|function|export\s+function|export\s+const)\s+([a-zA-Z0-9_]+)", code)
    exports = [e for e in exports if not e.startswith("_")][:8]
    dep_text = ", ".join(deps[:5]) if deps else "standard library modules"
    exp_text = ", ".join(exports[:4]) if exports else "module-level handlers"
    risks = []
    if "SELECT " in code or "INSERT " in code or "execute(" in code:
        risks.append("Database query execution detected — verify parameterized queries and connection pooling.")
    if "auth" in path.lower() or "login" in code.lower() or "token" in code.lower() or "password" in code.lower():
        risks.append("Authentication/credential handling path — enforce rate limiting and token expiration checks.")
    if "except Exception" in code or "except:" in code:
        risks.append("Broad exception handling detected — ensure errors are logged and not silently swallowed.")
    if not risks:
        risks.append("Add edge-case unit test coverage before release deployment.")
    return NodeSummaryResult(
        summary=[
            f"Implements {Path(path).name} ({loc} non-empty lines) exposing {exp_text}.",
            f"Integrates with {dep_text}.",
            "Participates in the Release Domino runtime and dependency graph.",
        ],
        purpose=f"Provides core implementation logic for {Path(path).name} ({exp_text}).",
        exports=exports,
        risks=risks,
    )


async def summarize_node(
    code: str,
    path: str,
    deps: list[str] | None = None,
    lang: str | None = None,
) -> NodeSummaryResult:
    """Summarize a single code node into 3 bullets, purpose, exports, and risks.

    Args:
        code: Raw source code of the file.
        path: Relative file path inside the repo.
        deps: List of module names or node IDs this file imports.
        lang: Optional language code ('py', 'ts', 'js', 'other').

    Returns:
        NodeSummaryResult with 3 bullets, purpose, exports, and risks.
    """
    deps_list = deps or []
    detected_lang = lang or _detect_language(path)
    trimmed = trim_code(code)

    prompt = SUMMARIZE_NODE_PROMPT.format(
        path=path,
        lang=detected_lang,
        deps=", ".join(deps_list) if deps_list else "none",
        code=trimmed,
    )

    result = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=NodeSummaryResult,
        fallback_factory=lambda: _build_fallback_summary(trimmed, path, deps_list),
    )
    return result


async def prewarm_summaries(
    project_id: str,
    nodes: list[dict[str, Any]],
    get_node_code: Callable[[str], str],
    emit_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, NodeSummaryResult]:
    """Pre-warm summaries in the background for changed nodes and crown jewels.

    Emits `summary_ready` via emit_event as each node summary finishes.
    """
    results: dict[str, NodeSummaryResult] = {}
    priority_nodes = [
        n for n in nodes
        if n.get("status") == "changed" or n.get("is_crown_jewel") is True
    ]

    for node in priority_nodes:
        node_id = str(node.get("id", ""))
        path = str(node.get("path", node_id))
        deps = list(node.get("deps", []))
        lang = node.get("lang")
        try:
            code = await asyncio.to_thread(get_node_code, node_id)
            summary = await summarize_node(code=code, path=path, deps=deps, lang=lang)
            results[node_id] = summary

            if emit_event is not None:
                await emit_event({
                    "type": "summary_ready",
                    "project_id": project_id,
                    "payload": {
                        "node_id": node_id,
                        "summary": summary.summary,
                        "purpose": summary.purpose,
                        "exports": summary.exports,
                        "risks": summary.risks,
                    },
                    "ts": time.time(),
                })
        except Exception as exc:
            logger.warning("Pre-warm failed for project=%s node=%s: %s", project_id, node_id, exc)

    return results