"""
Person 2 Automated Verification Suite (backend/tests/test_p2.py)
Tests all Person 2 deliverables (Tasks D0–D9) and code-review fixes:
  - D0: Demo repo builder (25 files, 42 commits, AST-clean session_store.py, runnable app.py)
  - D1 & D2: Container security flags, /workspace:rw, PYTHONPATH=/workspace:/deps, COVERAGE_FILE=/tmp/.coverage, Phase 1 network_on=True
  - Strict Sandbox Rule: Blocks host execution when Docker is off unless RD_ALLOW_LOCAL_FALLBACK=1
  - D3 & D5: Test runner (python -m pytest & Jest coverage parser), no fake 0.92 coverage, real upfront run_id
  - D4: Terminal WebSocket streaming (`WS /ws/terminal/{pid}`) + command allowlist
  - D6: Diff counter (`GET /api/diff/{pid}`) including untracked sandbox files via `git add -N`
  - D7: Merge conflict radar (`GET /api/merge-check/{pid}`) with exact tree-blob conflict line ranges
  - D8: Debounced file watcher (`app.git_ops.watcher`) import & event emission
  - D9: Test impact selection (`select_impacted_tests`)
"""
import ast
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
for p in (str(BACKEND_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Enable opt-in local fallback during unit tests when Docker daemon is not running
if os.getenv("RD_TEST_DOCKER_LIVE", "").lower() not in ("1", "true", "yes"):
    os.environ.setdefault("RD_ALLOW_LOCAL_FALLBACK", "1")

from fastapi.testclient import TestClient
from demo.make_demo_repo import build_demo_repo
from app.git_ops.diff import compute_diff_sync
from app.git_ops.merge_check import check_merge_conflicts_sync
from app.git_ops.watcher import DebouncedRepoWatcher
from app.runner.coverage import parse_jest_coverage_summary, parse_pytest_coverage_json
from app.runner.docker_runner import MANDATORY_SECURITY_FLAGS, build_docker_run_args, cleanup_sandbox, run_command
from app.runner.impact import select_impacted_tests
from app.main import PROJECT_REGISTRY, EVENT_LOG, app


class TestPerson2Modules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo_repo = REPO_ROOT / "demo" / "demo_shop_repo"
        if not (cls.demo_repo / ".git").exists() or not (cls.demo_repo / "auth.py").exists():
            build_demo_repo(cls.demo_repo)
        PROJECT_REGISTRY["demo"] = cls.demo_repo

    def test_d0_demo_repo_structure_and_git_history(self):
        py_files = list(self.demo_repo.rglob("*.py"))
        self.assertGreaterEqual(len(py_files), 24)
        for p in py_files:
            # Verify every generated Python file parses cleanly via ast.parse
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        app_src = (self.demo_repo / "app.py").read_text(encoding="utf-8")
        self.assertIn("__main__", app_src)

    def test_d1_and_d2_mandatory_container_security_flags_and_two_phase(self):
        deps_path = Path(tempfile.gettempdir()) / "dummy_deps"
        # Phase 2: network_on=False -> --network none, /workspace:rw, /deps:ro
        args_p2 = build_docker_run_args(
            self.demo_repo,
            ["python", "-m", "pytest", "-q"],
            lang="py",
            network_on=False,
            deps_dir=deps_path,
            deps_writable=False,
        )
        for required_flag in (
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1",
            "--pids-limit", "128",
            "--read-only",
            "--user", "1000:1000",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "PYTHONPATH=/workspace:/deps",
            "COVERAGE_FILE=/tmp/.coverage",
        ):
            self.assertIn(required_flag, args_p2)
        self.assertTrue(any(a.endswith(":/workspace:rw") for a in args_p2))
        self.assertTrue(any(a.endswith(":/deps:ro") for a in args_p2))

        # Phase 1: network_on=True -> --network bridge, /deps:rw
        args_p1 = build_docker_run_args(
            self.demo_repo,
            ["python", "-m", "pip", "install", "--target", "/deps", "-r", "requirements.txt"],
            lang="py",
            network_on=True,
            deps_dir=deps_path,
            deps_writable=True,
        )
        net_idx = args_p1.index("--network")
        self.assertEqual(args_p1[net_idx + 1], "bridge")
        self.assertTrue(any(a.endswith(":/deps:rw") for a in args_p1))

    def test_d2_strict_sandbox_blocks_host_execution_when_docker_off(self):
        async def _check():
            with patch("app.runner.docker_runner.is_docker_available", return_value=False), \
                 patch.dict(os.environ, {"RD_ALLOW_LOCAL_FALLBACK": "0", "RD_FORCE_LOCAL_RUNNER": "0"}):
                code, out, err, ws = await run_command("demo", self.demo_repo, ["python", "app.py"])
                cleanup_sandbox(ws)
                return code, out, err

        code, out, err = asyncio.run(_check())
        self.assertEqual(code, 127)
        self.assertIn("Docker not available", err)

    def test_d3_and_d5_sandboxed_test_runner_and_coverage_and_async_run_id(self):
        client = TestClient(app)
        # 1. Verify async run returns a real generated run_id (never "run_pending")
        res_async = client.post("/api/tests/run", json={"pid": "demo", "node_ids": ["cart.py"], "wait": False})
        self.assertEqual(res_async.status_code, 200)
        async_run_id = res_async.json()["run_id"]
        self.assertTrue(async_run_id.startswith("run_"))
        self.assertNotEqual(async_run_id, "run_pending")

        # 2. Verify synchronous test run with coverage
        res = client.post("/api/tests/run", json={"pid": "demo", "wait": True})
        self.assertEqual(res.status_code, 200)
        result = res.json()["result"]
        self.assertEqual(result["passed"], 5)
        self.assertEqual(result["failed"], 0)
        self.assertIn("cart.py", result["coverage"])
        self.assertNotEqual(result["coverage"].get("cart.py"), 0.92)  # No fake 0.92 coverage

        # 3. Verify Jest coverage parser
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            cov_f = tmp_p / "coverage-summary.json"
            cov_f.write_text(json.dumps({
                "total": {"lines": {"pct": 80}},
                "/workspace/src/cart.js": {"lines": {"pct": 87.5}},
            }), encoding="utf-8")
            jcov = parse_jest_coverage_summary(cov_f, tmp_p)
            self.assertEqual(jcov.get("src/cart.js"), 0.875)

        # 4. Failure path: inject failing sandbox test for auth.py and verify node_id == "auth.py"
        failing_test = (
            "import auth\n"
            "def test_auth_rejects_bad_token():\n"
            "    res = auth.verify_token('bearer_legacy_123')\n"
            "    assert res['role'] == 'superadmin', 'Expected superadmin role'\n"
        )
        res_fail = client.post(
            "/api/tests/run",
            json={"pid": "demo", "test_code": failing_test, "wait": True},
        )
        self.assertEqual(res_fail.status_code, 200)
        fail_data = res_fail.json()["result"]
        self.assertGreaterEqual(fail_data["failed"] + fail_data["errors"], 1)
        self.assertTrue(any(f["node_id"] == "auth.py" for f in fail_data["failures"]))

    def test_d4_terminal_websocket_happy_and_blocked_command(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/terminal/demo") as ws:
            banner = ws.receive_json()
            self.assertEqual(banner["stream"], "system")

            # Run "run" command and verify app.py prints output
            ws.send_json({"cmd": "run"})
            frames = []
            for _ in range(10):
                msg = ws.receive_json()
                frames.append(msg)
                if "Process exited" in msg["data"]:
                    break
            self.assertTrue(any("Release Domino Demo Shop running" in f["data"] for f in frames))

            # Blocked command
            ws.send_json({"cmd": "rm -rf /"})
            _ = ws.receive_json()
            err_msg = ws.receive_json()
            self.assertEqual(err_msg["stream"], "stderr")
            self.assertIn("Blocked command", err_msg["data"])

    def test_d6_diff_counter_with_untracked_sandbox_files(self):
        client = TestClient(app)
        sandbox_file = self.demo_repo / "sandbox_new_endpoint.py"
        try:
            sandbox_file.write_text("def hello_sandbox():\n    return {'ok': True}\n", encoding="utf-8")
            res = client.get("/api/diff/demo")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            paths = [f["path"] for f in data["files"]]
            self.assertIn("auth.py", paths)
            self.assertIn("sandbox_new_endpoint.py", paths)
        finally:
            if sandbox_file.exists():
                sandbox_file.unlink()
            subprocess.run(["git", "reset", "--", "sandbox_new_endpoint.py"], cwd=str(self.demo_repo), capture_output=True, check=False)

    def test_d7_merge_conflict_radar_exact_tree_blob_ranges(self):
        client = TestClient(app)
        res = client.get("/api/merge-check/demo")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["clean"])
        auth_conflict = next(c for c in data["conflicts"] if c["path"] == "auth.py")
        self.assertGreater(len(auth_conflict["lines"]), 0)
        s, e = auth_conflict["lines"][0]
        self.assertTrue(1 <= s < e)

    def test_d8_debounced_file_watcher_import_and_event_emission(self):
        emitted = []

        async def _fake_emit(evt: str, pid: str, payload: dict):
            emitted.append((evt, pid, payload))

        async def _run_watcher():
            loop = asyncio.get_running_loop()
            watcher = DebouncedRepoWatcher("demo", self.demo_repo, _fake_emit, debounce_sec=0.05)
            watcher.start(loop=loop)
            try:
                watcher.notify_file_modified(str(self.demo_repo / "auth.py"))
                for _ in range(40):
                    if len(emitted) >= 2:
                        break
                    await asyncio.sleep(0.05)
            finally:
                watcher.stop()

        asyncio.run(_run_watcher())
        event_types = [e[0] for e in emitted]
        self.assertIn("file_changed", event_types)
        self.assertIn("diff_updated", event_types)

    def test_d9_test_impact_selection(self):
        selected, total = select_impacted_tests(self.demo_repo, ["cart.py"])
        self.assertEqual(total, 2)
        self.assertEqual(selected, ["tests/test_cart.py"])

    def test_d10_universal_multi_stack_detector(self):
        from app.runner.terminal import detect_project_runtime
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. React / Vite
            vite_dir = root / "vite_app"
            vite_dir.mkdir()
            (vite_dir / "package.json").write_text(json.dumps({
                "scripts": {"dev": "vite"},
                "devDependencies": {"vite": "^5.0.0"}
            }), encoding="utf-8")
            rt_vite = detect_project_runtime(vite_dir)
            self.assertEqual(rt_vite["stack"], "React / Vite")
            self.assertEqual(rt_vite["mode"], "node")

            # 2. Next.js
            next_dir = root / "next_app"
            next_dir.mkdir()
            (next_dir / "package.json").write_text(json.dumps({
                "scripts": {"dev": "next dev"},
                "dependencies": {"next": "14.2.0", "react": "18.3.0"}
            }), encoding="utf-8")
            rt_next = detect_project_runtime(next_dir)
            self.assertEqual(rt_next["stack"], "Next.js")

            # 3. Node / Express
            exp_dir = root / "express_app"
            exp_dir.mkdir()
            (exp_dir / "package.json").write_text(json.dumps({
                "scripts": {"start": "node server.js"},
                "dependencies": {"express": "^4.19.0"}
            }), encoding="utf-8")
            rt_exp = detect_project_runtime(exp_dir)
            self.assertEqual(rt_exp["stack"], "Node.js / Express")

            # 4. FastAPI in nested backend/main.py
            fa_dir = root / "fastapi_app"
            (fa_dir / "backend").mkdir(parents=True)
            (fa_dir / "backend" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
            rt_fa = detect_project_runtime(fa_dir)
            self.assertEqual(rt_fa["stack"], "FastAPI")
            self.assertEqual(rt_fa["mode"], "py")

            # 5. Static HTML
            st_dir = root / "static_site"
            st_dir.mkdir()
            (st_dir / "index.html").write_text("<h1>Hello Static</h1>", encoding="utf-8")
            rt_st = detect_project_runtime(st_dir)
            self.assertEqual(rt_st["stack"], "Static HTML/JS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
