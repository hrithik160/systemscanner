"""
Task D5 — Sandboxed Test & Coverage Runner (backend/app/runner/tests.py)
Runs `python -m pytest --cov=. --cov-report=json` (Python) or `jest --coverage` (Node/JS)
inside the sandboxed runner, parses real per-file coverage and failure messages (never inventing
fake coverage numbers), maps failed tests back to relative-path node IDs, and emits
`coverage_updated` and `test_run_finished`.
"""
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, List, Optional

from shared.models import TestFailure, TestRunResult
from app.runner.coverage import parse_jest_coverage_summary, parse_pytest_coverage_json
from app.runner.docker_runner import cleanup_sandbox, run_command
from app.runner.impact import select_impacted_tests

logger = logging.getLogger("release_domino.runner.tests")

SUMMARY_COUNTS_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors)")
FAILURE_LINE_RE = re.compile(r"^FAILED\s+([^\s]+?)(?:\s+-\s+(.+))?$")

STDLIB_TEST_SHIM = '''import contextlib, importlib.util, json, pathlib, sys, trace, types

@contextlib.contextmanager
def _raises(exc_type):
    try:
        yield
    except exc_type:
        return
    raise AssertionError(f"DID NOT RAISE {exc_type}")

if "pytest" not in sys.modules:
    sys.modules["pytest"] = types.SimpleNamespace(raises=_raises)

cov_out = sys.argv[1]
test_files = sys.argv[2:]
root = pathlib.Path.cwd()
if not test_files:
    test_files = sorted(str(p.relative_to(root)) for p in (root / "tests").glob("test_*.py"))

passed = failed = errors = 0
tracer = trace.Trace(count=1, trace=0)

def _run_all():
    global passed, failed, errors
    for rel in test_files:
        p = root / rel
        if not p.exists():
            continue
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            errors += 1
            print(f"FAILED {rel}::<module> - {e}")
            continue
        for name in sorted(dir(mod)):
            if name.startswith("test_") and callable(getattr(mod, name)):
                fn = getattr(mod, name)
                try:
                    fn()
                    passed += 1
                    print(f"PASSED {rel}::{name}")
                except AssertionError as e:
                    failed += 1
                    msg = str(e) or "AssertionError"
                    print(f"FAILED {rel}::{name} - {msg}")
                except Exception as e:
                    errors += 1
                    print(f"FAILED {rel}::{name} - {type(e).__name__}: {e}")

tracer.runfunc(_run_all)
results = tracer.results()
counts = results.counts

files_cov = {}
for py_file in root.glob("*.py"):
    if py_file.name.startswith("_rd_"):
        continue
    lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
    executable_lines = [
        idx for idx, line in enumerate(lines, 1)
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith('"""')
    ]
    if not executable_lines:
        continue
    hit = sum(1 for ln in executable_lines if counts.get((str(py_file.resolve()), ln), 0) > 0 or counts.get((str(py_file), ln), 0) > 0)
    if hit > 0:
        pct = round((hit / len(executable_lines)) * 100.0, 1)
        files_cov[py_file.name] = {"summary": {"percent_covered": pct}}

pathlib.Path(cov_out).write_text(json.dumps({"files": files_cov}), encoding="utf-8")
print(f"=== {passed} passed, {failed} failed, {errors} errors ===")
sys.exit(1 if (failed or errors) else 0)
'''


def _parse_pytest_counts(output: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    for m in SUMMARY_COUNTS_RE.finditer(output):
        count = int(m.group(1))
        kind = m.group(2)
        if kind == "passed":
            passed = count
        elif kind == "failed":
            failed = count
        elif kind in ("error", "errors"):
            errors = count
    return passed, failed, errors


def _infer_target_node_id(
    test_file: str,
    path_to_node_id: Dict[str, str],
    sandbox_ws: Optional[Path] = None,
    fallback_node_ids: Optional[List[str]] = None,
    ext: str = ".py",
) -> str:
    stem = Path(test_file).stem
    if stem.startswith("test_"):
        target_mod = stem[5:] + ext
    elif stem.endswith("_test"):
        target_mod = stem[:-5] + ext
    elif stem.endswith(".test") or stem.endswith(".spec"):
        target_mod = stem[:-5] + ext
    else:
        target_mod = stem + ext

    if sandbox_ws and not (sandbox_ws / target_mod).exists():
        # Check imports inside the test file to map generated sandbox tests to the real module
        tf_path = sandbox_ws / test_file
        if tf_path.exists():
            src = tf_path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", src, re.MULTILINE):
                mod_name = m.group(1)
                if mod_name in ("pytest", "unittest", "json", "os", "sys"):
                    continue
                candidate = f"{mod_name}{ext}"
                if (sandbox_ws / candidate).exists():
                    target_mod = candidate
                    break
        if (not (sandbox_ws / target_mod).exists()) and fallback_node_ids:
            target_mod = fallback_node_ids[0]

    return path_to_node_id.get(target_mod) or path_to_node_id.get(test_file) or target_mod


def _parse_pytest_failures(
    output: str,
    path_to_node_id: Dict[str, str],
    sandbox_ws: Optional[Path] = None,
    fallback_node_ids: Optional[List[str]] = None,
) -> List[TestFailure]:
    failures: List[TestFailure] = []
    for line in output.splitlines():
        m = FAILURE_LINE_RE.match(line.strip())
        if m:
            test_id = m.group(1).replace("\\", "/")
            msg = m.group(2) or "Test assertion failed"
            test_file = test_id.split("::")[0]
            node_id = _infer_target_node_id(
                test_file, path_to_node_id, sandbox_ws=sandbox_ws, fallback_node_ids=fallback_node_ids, ext=".py"
            )
            failures.append(TestFailure(test=test_id, node_id=node_id, message=msg))
    return failures


def _detect_test_mode(repo_path: Path, selected_tests: List[str], explicit_lang: Optional[str]) -> str:
    if explicit_lang in ("py", "node"):
        return explicit_lang
    if selected_tests and all(t.endswith((".js", ".ts", ".jsx", ".tsx")) for t in selected_tests):
        return "node"
    if (repo_path / "package.json").exists() and not any(t.endswith(".py") for t in selected_tests):
        return "node"
    return "py"


async def run_tests(
    pid: str,
    repo_path: Any = None,
    node_ids: Any = None,
    test_code: Optional[str] = None,
    path_to_node_id: Optional[Dict[str, str]] = None,
    emit_event: Optional[Callable[[str, str, dict], Awaitable[None]]] = None,
    on_terminal_line: Optional[Callable[[str, str], Awaitable[None]]] = None,
    run_id: Optional[str] = None,
    lang: Optional[str] = None,
    install_deps: bool = False,
    strict_docker: bool = False,
    keep_alive_sec: int = 0,
    **kwargs: Any,
) -> TestRunResult:
    pid = pid or kwargs.get("project_id", "demo")
    """
    Executes `python -m pytest --cov=. --cov-report=json` (or `jest --coverage` for JS/TS)
    inside the sandboxed runner, parses real coverage and failures, and emits
    `coverage_updated` and `test_run_finished`.
    """
    # Support Person 1s 3-argument call signature: run_tests(pid, [node_id], test_code)
    if isinstance(repo_path, list):
        if isinstance(node_ids, str) and test_code is None:
            test_code = node_ids
        node_ids = repo_path
        repo_path = None
    if repo_path is None or not isinstance(repo_path, Path):
        try:
            from app.main import PROJECT_REGISTRY, DEMO_REPO_PATH
            repo_path = Path(repo_path) if isinstance(repo_path, str) else PROJECT_REGISTRY.get(pid, DEMO_REPO_PATH)
        except Exception:
            repo_path = Path(".")

    run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
    start_ts = time.perf_counter()
    path_map = path_to_node_id or {}

    extra_files: Dict[str, str] = {}
    selected_tests, total_tests = select_impacted_tests(repo_path, node_ids or [])
    mode = _detect_test_mode(repo_path, selected_tests, lang)

    if test_code:
        gen_test_path = "tests/test_generated_sandbox.test.js" if mode == "node" else "tests/test_generated_sandbox.py"
        extra_files[gen_test_path] = test_code
        selected_tests = [gen_test_path]

    if mode == "node":
        jest_out = "rd_jest_out.json"
        cmd = [
            "jest",
            "--coverage",
            "--coverageReporters=json-summary",
            "--json",
            f"--outputFile={jest_out}",
        ]
        if selected_tests:
            cmd.extend(selected_tests)

        exit_code, stdout_text, stderr_text, sandbox_ws = await run_command(
            pid=pid,
            repo_path=repo_path,
            cmd_args=cmd,
            mode="node",
            on_line=on_terminal_line,
            extra_files=extra_files,
            install_deps=install_deps,
            strict_docker=strict_docker,
            keep_alive_sec=keep_alive_sec,
        )
        try:
            duration_s = round(time.perf_counter() - start_ts, 3)
            passed = failed = errors = 0
            failures: List[TestFailure] = []
            jest_json_path = sandbox_ws / jest_out
            if jest_json_path.exists():
                try:
                    jdata = json.loads(jest_json_path.read_text(encoding="utf-8"))
                    passed = int(jdata.get("numPassedTests", 0))
                    failed = int(jdata.get("numFailedTests", 0))
                    errors = int(jdata.get("numRuntimeErrorTestSuites", 0))
                    for suite in jdata.get("testResults", []):
                        s_name = str(suite.get("name", "")).replace("\\", "/")
                        for assertion in suite.get("assertionResults", []):
                            if assertion.get("status") == "failed":
                                title = assertion.get("fullName") or assertion.get("title") or "jest_test"
                                msg = "; ".join(assertion.get("failureMessages") or ["Assertion failed"])
                                node_id = _infer_target_node_id(s_name, path_map, sandbox_ws=sandbox_ws, fallback_node_ids=node_ids, ext=".js")
                                failures.append(TestFailure(test=f"{Path(s_name).name}::{title}", node_id=node_id, message=msg[:300]))
                except Exception as exc:
                    logger.warning("Failed to parse Jest JSON output: %s", exc)
                    errors = 1
            elif exit_code != 0:
                errors = 1
                failures.append(TestFailure(test="runner::jest", node_id=None, message=(stderr_text or stdout_text).strip()[:300]))

            cov_map = parse_jest_coverage_summary(sandbox_ws / "coverage" / "coverage-summary.json", sandbox_ws)
            result = TestRunResult(
                run_id=run_id,
                passed=passed,
                failed=failed,
                errors=errors,
                duration_s=duration_s,
                coverage=cov_map,
                failures=failures,
                selected_tests=len(selected_tests),
                total_tests=total_tests,
            )
            if emit_event:
                await emit_event("coverage_updated", pid, {"coverage": cov_map})
                await emit_event("test_run_finished", pid, result.model_dump())
            return result
        finally:
            cleanup_sandbox(sandbox_ws)

    # Python mode: always invoke `python -m pytest` so `/workspace` is on sys.path
    cov_filename = "rd_coverage_out.json"
    cmd = ["python", "-m", "pytest", "--cov=.", f"--cov-report=json:{cov_filename}", "-v"]
    if selected_tests:
        cmd.extend(selected_tests)

    exit_code, stdout_text, stderr_text, sandbox_ws = await run_command(
        pid=pid,
        repo_path=repo_path,
        cmd_args=cmd,
        mode="py",
        on_line=on_terminal_line,
        extra_files=extra_files,
        install_deps=install_deps,
        strict_docker=strict_docker,
        keep_alive_sec=keep_alive_sec,
    )

    combined_initial = stdout_text + "\n" + stderr_text
    if "unrecognized arguments: --cov" in combined_initial:
        cleanup_sandbox(sandbox_ws)
        plain_cmd = ["python", "-m", "pytest", "-v"] + (selected_tests if selected_tests else [])
        exit_code, stdout_text, stderr_text, sandbox_ws = await run_command(
            pid=pid,
            repo_path=repo_path,
            cmd_args=plain_cmd,
            mode="py",
            on_line=on_terminal_line,
            extra_files=extra_files,
        )
    elif "No module named pytest" in combined_initial:
        cleanup_sandbox(sandbox_ws)
        shim_files = dict(extra_files)
        shim_files["_rd_stdlib_pytest.py"] = STDLIB_TEST_SHIM
        shim_cmd = ["python", "_rd_stdlib_pytest.py", cov_filename] + (selected_tests if selected_tests else [])
        exit_code, stdout_text, stderr_text, sandbox_ws = await run_command(
            pid=pid,
            repo_path=repo_path,
            cmd_args=shim_cmd,
            mode="py",
            on_line=on_terminal_line,
            extra_files=shim_files,
        )

    try:
        duration_s = round(time.perf_counter() - start_ts, 3)
        combined_out = stdout_text + "\n" + stderr_text
        passed, failed, errors = _parse_pytest_counts(combined_out)
        if exit_code != 0 and failed == 0 and errors == 0:
            errors = 1

        # Parse real coverage JSON only — never invent fake fallback percentages
        cov_map = parse_pytest_coverage_json(sandbox_ws / cov_filename, sandbox_ws)
        failures = _parse_pytest_failures(combined_out, path_map, sandbox_ws=sandbox_ws, fallback_node_ids=node_ids)
        if exit_code == 127 and not failures:
            failures.append(TestFailure(test="runner::docker", node_id=None, message=stderr_text.strip()))

        result = TestRunResult(
            run_id=run_id,
            passed=passed,
            failed=failed,
            errors=errors,
            duration_s=duration_s,
            coverage=cov_map,
            failures=failures,
            selected_tests=len(selected_tests),
            total_tests=total_tests,
        )

        if emit_event:
            await emit_event("coverage_updated", pid, {"coverage": cov_map})
            await emit_event("test_run_finished", pid, result.model_dump())

        return result
    finally:
        cleanup_sandbox(sandbox_ws)
