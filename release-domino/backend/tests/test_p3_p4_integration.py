"""
End-to-End Integration Tests for Person 3 (Graph, Defect Mining, Blast Radius, Risk Engine, Report)
and Person 4 (React Flow Frontend Bundle & UI Contract Endpoints).
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
for p in (str(BACKEND_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from demo.make_demo_repo import build_demo_repo
from app.main import PROJECT_REGISTRY, app


class TestP3AndP4Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo_repo = REPO_ROOT / "demo" / "demo_shop_repo"
        if not (cls.demo_repo / ".git").exists() or not (cls.demo_repo / "auth.py").exists():
            build_demo_repo(cls.demo_repo)
        PROJECT_REGISTRY["demo"] = cls.demo_repo
        cls.client = TestClient(app)

    def test_01_react_flow_frontend_served_at_root_and_assets(self):
        # Browser request (Accept: text/html) gets the compiled React Flow frontend
        r_html = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(r_html.status_code, 200)
        self.assertIn('<div id="root"></div>', r_html.text)
        self.assertIn('/assets/bundle.js', r_html.text)

        # API client request gets JSON health check
        r_json = self.client.get("/", headers={"Accept": "application/json"})
        self.assertEqual(r_json.status_code, 200)
        self.assertEqual(r_json.json()["status"], "ok")

        # Static bundle.js and style.css exist and serve 200 OK
        r_js = self.client.get("/assets/bundle.js")
        self.assertEqual(r_js.status_code, 200)
        self.assertGreater(len(r_js.content), 100_000)

        r_css = self.client.get("/assets/style.css")
        self.assertEqual(r_css.status_code, 200)
        self.assertGreater(len(r_css.content), 20_000)

    def test_02_graph_and_risk_engine_endpoints(self):
        r_graph = self.client.get("/api/graph/demo")
        self.assertEqual(r_graph.status_code, 200)
        g = r_graph.json()
        self.assertEqual(g["project_id"], "demo")
        self.assertGreaterEqual(len(g["nodes"]), 10)
        self.assertGreaterEqual(len(g["edges"]), 5)

        r_risk = self.client.get("/api/risk/demo")
        self.assertEqual(r_risk.status_code, 200)
        rk = r_risk.json()
        self.assertIn(rk["verdict"], ("GO", "CAUTION", "HOLD"))
        self.assertGreaterEqual(rk["score"], 0)
        self.assertLessEqual(rk["score"], 100)
        self.assertTrue(len(rk["factors"]) >= 4)
        self.assertTrue(len(rk["reasons"]) >= 1)

    def test_03_node_detail_crown_jewel_and_code_edit(self):
        r_node = self.client.get("/api/node/demo/auth.py")
        self.assertEqual(r_node.status_code, 200)
        nd = r_node.json()
        self.assertIn("code", nd)
        self.assertIn("defect_history", nd)

        # Toggle Crown Jewel
        r_cj = self.client.post("/api/node/demo/auth.py/crown-jewel", json={"is_crown_jewel": True})
        self.assertEqual(r_cj.status_code, 200)
        self.assertTrue(r_cj.json()["node"]["is_crown_jewel"])

    def test_04_sandbox_node_and_connection_wiring(self):
        r_sb = self.client.post(
            "/api/sandbox/node",
            json={
                "pid": "demo",
                "name": "rate_limiter_sandbox.py",
                "code": "def check_rate_limit(ip: str) -> bool:\n    return True\n",
                "lang": "py",
                "is_crown_jewel": False,
            },
        )
        self.assertEqual(r_sb.status_code, 200)
        sb_data = r_sb.json()
        self.assertEqual(sb_data["node"]["kind"], "sandbox")

        # Propose connection via Person 1 LLM endpoint using `from` / `to` alias
        r_conn = self.client.post(
            "/api/sandbox/connect",
            json={
                "pid": "demo",
                "from": "auth.py",
                "to": "rate_limiter_sandbox.py",
            },
        )
        self.assertEqual(r_conn.status_code, 200)
        prop_id = r_conn.json()["proposal_id"]

        # Apply proposal
        r_app = self.client.post(
            "/api/sandbox/apply",
            json={"pid": "demo", "proposal_id": prop_id},
        )
        self.assertEqual(r_app.status_code, 200)
        self.assertEqual(r_app.json()["status"], "applied")

    def test_05_release_report_and_comparison_endpoints(self):
        r_md = self.client.get("/api/report/demo?format=md")
        self.assertEqual(r_md.status_code, 200)
        self.assertIn("# Release Domino", r_md.text)

        r_html = self.client.get("/api/report/demo?format=html")
        self.assertEqual(r_html.status_code, 200)
        self.assertIn("<!DOCTYPE html>", r_html.text)

        r_cmp = self.client.get("/api/compare/demo?base=origin/main&head=HEAD")
        self.assertEqual(r_cmp.status_code, 200)
        cmp_data = r_cmp.json()
        self.assertEqual(cmp_data["project_id"], "demo")
        self.assertTrue(len(cmp_data["deltas"]) > 0)


if __name__ == "__main__":
    unittest.main()
