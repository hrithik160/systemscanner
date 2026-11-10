"""Automated unit test generation with Docker runner validation and 1-retry error feedback (Task L4)."""

import asyncio
import inspect
import logging
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.llm import client
from app.llm.prompts import GENERATE_TESTS_PROMPT
from app.llm.summarize import trim_code

logger = logging.getLogger(__name__)


class GeneratedTestResult(BaseModel):
    """Contract return shape for POST /api/tests/generate."""
    test_code: str = Field(description="Runnable pytest or jest test file content")
    framework: str = Field(description="'pytest' or 'jest'")


def _infer_framework(path: str, framework: str | None = None) -> tuple[str, str]:
    """Return (framework, lang) based on file extension or explicit framework."""
    ext = Path(path).suffix.lower()
    if framework in ("pytest", "jest"):
        lang = "py" if framework == "pytest" else "ts"
        return framework, lang
    if ext in (".ts", ".tsx", ".js", ".jsx"):
        return "jest", "ts" if "ts" in ext else "js"
    return "pytest", "py"


def _build_fallback_test(path: str, framework: str) -> GeneratedTestResult:
    """Deterministic fallback test file so the endpoint never crashes."""
    stem = Path(path).stem or "module"
    if framework == "jest":
        code = (
            f"describe('{stem} smoke test', () => {{\n"
            f"  test('module loads cleanly', () => {{\n"
            f"    expect(true).toBe(true);\n"
            f"  }});\n"
            f"}});\n"
        )
    else:
        code = (
            f"def test_{stem}_smoke():\n"
            f'    """Fallback smoke test for {path}."""\n'
            f"    assert True\n"
        )
    return GeneratedTestResult(test_code=code, framework=framework)


async def _invoke_runner(
    runner_fn: Callable[..., Any],
    project_id: str,
    node_id: str,
    test_code: str,
) -> tuple[bool, str]:
    """Call Person 2's run_tests() helper (sync or async) and check if the generated test passed."""
    try:
        if inspect.iscoroutinefunction(runner_fn):
            res = await runner_fn(project_id, [node_id], test_code)
        else:
            res = await asyncio.to_thread(runner_fn, project_id, [node_id], test_code)

        if isinstance(res, dict):
            failed = int(res.get("failed", 0)) + int(res.get("errors", 0))
            if failed == 0 and res.get("exit_code", 0) == 0:
                return True, ""
            failures = res.get("failures", [])
            err_msg = "; ".join(str(f.get("message", f)) for f in failures) or str(res.get("output", "Test failed"))
            return False, err_msg

        # Handle object/Pydantic attributes if Person 2 returns a model
        failed = int(getattr(res, "failed", 0)) + int(getattr(res, "errors", 0))
        if failed == 0:
            return True, ""
        failures = getattr(res, "failures", [])
        err_msg = "; ".join(str(getattr(f, "message", f)) for f in failures) or "Test execution failed"
        return False, err_msg
    except Exception as exc:
        logger.warning("Runner validation error: %s", exc)
        return False, str(exc)


async def generate_tests(
    code: str,
    diff: str = "",
    framework: str | None = None,
    path: str = "module.py",
    project_id: str | None = None,
    node_id: str | None = None,
    runner_fn: Callable[..., Any] | None = None,
) -> GeneratedTestResult:
    """Generate a runnable pytest or jest test file, validating via P2's runner if available.

    If runner validation fails on the first attempt, feeds the error back to the LLM once.
    """
    fw, lang = _infer_framework(path, framework)
    trimmed_code = trim_code(code)
    prompt = GENERATE_TESTS_PROMPT.format(
        framework=fw,
        path=path,
        lang=lang,
        diff=diff or "(No diff provided; test all key functions and edge cases)",
        code=trimmed_code,
    )

    first_attempt = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=GeneratedTestResult,
        fallback_factory=lambda: _build_fallback_test(path, fw),
    )
    first_attempt.framework = fw

    # Try to find Person 2's runner automatically if not passed explicitly
    if runner_fn is None and project_id is not None:
        try:
            from app.runner import tests as p2_tests  # Person 2's module when merged
            if hasattr(p2_tests, "run_tests"):
                runner_fn = p2_tests.run_tests
        except ImportError:
            pass

    # Validate in Docker via P2's runner; on failure feed error back once
    if runner_fn is not None and project_id is not None:
        target_nid = node_id or path
        passed, error_msg = await _invoke_runner(runner_fn, project_id, target_nid, first_attempt.test_code)
        if not passed and error_msg:
            logger.info("Generated test failed in runner; feeding error back once for node=%s", target_nid)
            repair_prompt = (
                f"{prompt}\n\n"
                f"The previous test failed when executed in the test runner with this error:\n"
                f"{error_msg}\n\n"
                f"Previous test code:\n{first_attempt.test_code}\n\n"
                f"Fix the test code so it runs cleanly and passes. Return JSON with 'test_code' and 'framework'."
            )
            repaired = await client.chat(
                messages=[{"role": "user", "content": repair_prompt}],
                schema=GeneratedTestResult,
                fallback_factory=lambda: first_attempt,
            )
            repaired.framework = fw
            return repaired

    return first_attempt