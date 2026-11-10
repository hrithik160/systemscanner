"""Sandbox endpoint wiring proposals with style preservation, AST/JSX syntax validation, and auto-healing (Task L5)."""

import ast
import asyncio
import logging
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.llm import client
from app.llm.prompts import AUTO_HEAL_CODE_PROMPT, PROPOSE_CONNECTION_PROMPT
from app.llm.summarize import trim_code

logger = logging.getLogger(__name__)

# In-memory storage for pending proposals keyed by proposal_id
_PENDING_PROPOSALS: dict[str, dict[str, Any]] = {}

_VOID_HTML_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

_STYLE_IMPORT_RE = re.compile(
    r"""^\s*(?:import\s+[^;\n]*?['"][^'"]+\.(?:css|scss|sass|less)['"]\s*;?|const\s+\w+\s*=\s*require\(\s*['"][^'"]+\.(?:css|scss|sass|less)['"]\s*\)\s*;?|require\(\s*['"][^'"]+\.(?:css|scss|sass|less)['"]\s*\)\s*;?)""",
    re.MULTILINE,
)


class ConnectionProposalResult(BaseModel):
    """Contract return shape for connection proposals."""
    patch: str = Field(description="Valid unified-diff string")
    endpoint: str = Field(description="Function call, route, or import added")
    rationale: str = Field(description="Plain-English explanation of how it connects")


class SandboxConnectResponse(BaseModel):
    """Contract response for POST /api/sandbox/connect."""
    proposal_id: str
    patch: str
    endpoint: str
    rationale: str


class _HealedCodeSchema(BaseModel):
    healed_code: str
    fix_summary: str = ""


def _validate_style_preservation(orig_code: str, mod_code: str) -> str:
    """Programmatic safeguard that detects dropped CSS/SCSS imports and re-injects them automatically.
    Also works on unified diff patches by stripping accidental `-import '...css'` deletion lines.
    """
    if not orig_code or not mod_code:
        return mod_code

    # If mod_code is a unified diff patch, ensure it does not delete CSS/SCSS imports
    if mod_code.lstrip().startswith("--- ") and "+++ " in mod_code:
        cleaned_lines: list[str] = []
        for line in mod_code.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                stripped = line[1:].strip()
                if re.search(r"""['"][^'"]+\.(?:css|scss|sass|less)['"]""", stripped):
                    # Convert accidental deletion into context line so CSS import stays intact
                    cleaned_lines.append(" " + line[1:])
                    continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines) + ("\n" if mod_code.endswith("\n") else "")

    orig_imports = [m.group(0).strip() for m in _STYLE_IMPORT_RE.finditer(orig_code)]
    missing_imports = [imp for imp in orig_imports if imp not in mod_code]
    if missing_imports:
        logger.info("Re-injecting %d dropped CSS/style import(s) to preserve styling.", len(missing_imports))
        prefix = "\n".join(missing_imports) + "\n"
        return prefix + mod_code
    return mod_code


def _strip_js_comments_and_strings(code: str) -> str:
    """Replace JS/TS comments and string literals with spaces (preserving newlines) for bracket/tag scanning."""
    def _repl(match: re.Match) -> str:
        s = match.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in s)

    pattern = re.compile(
        r"//[^\n]*|/\*[\s\S]*?\*/|`(?:\\[\s\S]|[^`\\])*`|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\""
    )
    return pattern.sub(_repl, code)


def _validate_code_syntax(code: str, lang: str) -> tuple[bool, str]:
    """Validate Python via `ast.parse` or JS/TS/JSX/TSX via balanced brackets & JSX tag symmetry."""
    if not code or not code.strip():
        return True, ""

    clean_lang = (lang or "py").lower().lstrip(".")
    if clean_lang in ("py", "python"):
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"Python SyntaxError at line {exc.lineno}: {exc.msg}"

    if clean_lang in ("js", "jsx", "ts", "tsx", "javascript", "typescript"):
        scrubbed = _strip_js_comments_and_strings(code)
        # 1. Check balanced brackets (), {}, []
        pairs = {")": "(", "}": "{", "]": "["}
        openers = set(pairs.values())
        stack: list[tuple[str, int]] = []
        for line_no, line in enumerate(scrubbed.splitlines(), start=1):
            for ch in line:
                if ch in openers:
                    stack.append((ch, line_no))
                elif ch in pairs:
                    if not stack or stack[-1][0] != pairs[ch]:
                        return False, f"Unbalanced '{ch}' at line {line_no}"
                    stack.pop()
        if stack:
            unclosed_ch, unclosed_line = stack[-1]
            return False, f"Unclosed '{unclosed_ch}' opened at line {unclosed_line}"

        # 2. Check JSX open/close tag symmetry for common structural & component tags
        tag_re = re.compile(r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9_.]*)\b([^>]*?)(/?)>")
        jsx_stack: list[str] = []
        for match in tag_re.finditer(scrubbed):
            is_closing = bool(match.group(1))
            tag_name = match.group(2)
            rest_attrs = match.group(3) or ""
            is_self_closing = bool(match.group(4)) or rest_attrs.rstrip().endswith("/")
            if tag_name.lower() in _VOID_HTML_TAGS or is_self_closing:
                continue
            if not is_closing:
                jsx_stack.append(tag_name)
            else:
                if not jsx_stack:
                    return False, f"Unexpected closing JSX tag </{tag_name}> with no matching opening tag"
                if jsx_stack[-1] != tag_name:
                    return False, f"Mismatched JSX tag: expected </{jsx_stack[-1]}>, found </{tag_name}>"
                jsx_stack.pop()
        if jsx_stack:
            return False, f"Unclosed JSX tag <{jsx_stack[-1]}>"

    return True, ""


async def _auto_heal_code_if_needed(
    code: str,
    lang: str,
    orig_code: str = "",
) -> str:
    """Validate style preservation and syntax; if syntax fails, trigger LLM self-healing before output."""
    healed = _validate_style_preservation(orig_code, code) if orig_code else code
    valid, err_msg = _validate_code_syntax(healed, lang)
    if valid:
        return healed

    logger.warning("Pre-output validation caught syntax issue (%s); invoking auto-healer.", err_msg)
    prompt = AUTO_HEAL_CODE_PROMPT.format(
        lang=lang,
        error_msg=err_msg,
        code=trim_code(healed, max_chars=12000),
    )
    res = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=_HealedCodeSchema,
        fallback_factory=lambda: _HealedCodeSchema(
            healed_code=orig_code or healed,
            fix_summary="Restored syntactically valid baseline code.",
        ),
    )
    candidate = _validate_style_preservation(orig_code, res.healed_code) if orig_code else res.healed_code
    valid2, _ = _validate_code_syntax(candidate, lang)
    if valid2:
        return candidate
    return orig_code if orig_code else healed


def _validate_patch_syntax(patch: str, lang: str) -> bool:
    """Check if the code changes in the patch are syntactically valid."""
    try:
        added_lines = [
            line[1:] for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        snippet = "\n".join(added_lines)
        if not snippet.strip():
            return True
        if lang == "py":
            # Dedent or parse top-level statements if possible
            ast.parse("\n".join(l.strip() for l in added_lines if l.strip()))
            return True
        ok, _ = _validate_code_syntax(snippet, lang)
        return ok
    except SyntaxError as exc:
        logger.warning("Proposed patch contains invalid syntax: %s", exc)
        return False


def _build_fallback_proposal(src_path: str, dst_path: str, lang: str = "py") -> ConnectionProposalResult:
    """Deterministic fallback proposal if LLM fails, respecting language and preserving styles."""
    from app.llm.knowledge import compute_relative_import_path
    stem = Path(src_path).stem
    rel_path = compute_relative_import_path(dst_path, src_path, lang)
    if lang in ("js", "jsx", "ts", "tsx"):
        import_stmt = f"import {{ {stem} }} from '{rel_path}';"
        patch = (
            f"--- a/{dst_path}\n"
            f"+++ b/{dst_path}\n"
            f"@@ -1,3 +1,4 @@\n"
            f"+// Connected via Release Domino sandbox (styles preserved)\n"
            f"+{import_stmt}\n"
        )
    else:
        import_stmt = f"import {stem}"
        patch = (
            f"--- a/{dst_path}\n"
            f"+++ b/{dst_path}\n"
            f"@@ -1,3 +1,4 @@\n"
            f"+# Connected via Release Domino sandbox\n"
            f"+{import_stmt}\n"
        )
    return ConnectionProposalResult(
        patch=patch,
        endpoint=import_stmt,
        rationale=f"Automatically wires {src_path} into {dst_path} while preserving existing styling and layout.",
    )


async def propose_connection(
    src_code: str,
    dst_code: str,
    src_path: str = "sandbox_node.py",
    dst_path: str = "target_node.py",
    lang: str = "py",
) -> ConnectionProposalResult:
    """Propose how to wire a source file into a destination file, returning a style-preserving, syntax-validated diff patch."""
    ext = Path(dst_path).suffix.lower().lstrip(".")
    if ext in ("py", "js", "jsx", "ts", "tsx"):
        lang = ext

    trimmed_src = trim_code(src_code, max_chars=12000)
    trimmed_dst = trim_code(dst_code, max_chars=12000)

    prompt = PROPOSE_CONNECTION_PROMPT.format(
        lang=lang,
        src_path=src_path,
        src_code=trimmed_src,
        dst_path=dst_path,
        dst_code=trimmed_dst,
    )

    proposal = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=ConnectionProposalResult,
        fallback_factory=lambda: _build_fallback_proposal(src_path, dst_path, lang),
    )

    # Enforce style preservation on the proposed patch
    proposal.patch = _validate_style_preservation(dst_code, proposal.patch)

    # Validate syntax of proposed patch
    if not _validate_patch_syntax(proposal.patch, lang):
        logger.info("AI patch failed syntax check; falling back to safe default import patch.")
        proposal = _build_fallback_proposal(src_path, dst_path, lang)

    return proposal


def store_proposal(proposal_id: str, data: dict[str, Any]) -> None:
    _PENDING_PROPOSALS[proposal_id] = data


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    return _PENDING_PROPOSALS.get(proposal_id)


def remove_proposal(proposal_id: str) -> None:
    _PENDING_PROPOSALS.pop(proposal_id, None)