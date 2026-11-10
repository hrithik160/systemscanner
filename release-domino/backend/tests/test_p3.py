"""
Person 3 Unit Test Suite (backend/tests/test_p3.py)
Tests all Person 3 modules (`backend/app/analysis/`, `backtest/run_backtest.py`, `backend/app/events.py`, `backend/app/projects.py`):
  - B3: Python AST analyzer (`ast_py.py`) and JS/TS import/route scanner (`ast_js.py`)
  - B4: Defect mining formula (`defects.py`)
  - B5: Blast radius BFS over reversed edges (`blast.py`) on 3 graph topologies
  - B6: Section 6 Risk Engine formulas & exact worked example (`risk.py` -> score=77, verdict=HOLD)
  - B8: Historical Git Backtest (`backtest/run_backtest.py`) lift calculation
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

from shared.models import CEdge
from app.analysis.ast_py import analyze_python_source
from app.analysis.ast_js import analyze_js_ts_source
from app.analysis.defects import compute_defect_score, mine_git_defects_sync
from app.analysis.blast import compute_blast_radius
from app.analysis.risk import compute_node_risk_factors, compute_worked_example_score, score_to_verdict
from backtest.run_backtest import run_backtest
from demo.make_demo_repo import build_demo_repo


class TestPerson3AnalysisAndRisk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo_repo = REPO_ROOT / "demo" / "demo_shop_repo"
        if not (cls.demo_repo / ".git").exists() or not (cls.demo_repo / "auth.py").exists():
            build_demo_repo(cls.demo_repo)

    def test_b3_ast_python_and_js_analyzers(self):
        py_code = """
import redis
from fastapi import APIRouter
router = APIRouter()

@router.post("/login")
def login_user(username: str):
    return True
"""
        py_info = analyze_python_source(py_code, "app/login_route.py")
        self.assertIn("redis", py_info["imports"])
        self.assertIn("login_user", py_info["exports"])
        self.assertIn("login_user", py_info["routes"])
        self.assertIn("infra:redis", py_info["infra"])

        js_code = """
import express from 'express';
const redis = require('ioredis');
export function startServer() {}
app.get('/api/items', (req, res) => {});
"""
        js_info = analyze_js_ts_source(js_code, "src/server.ts")
        self.assertIn("express", js_info["imports"])
        self.assertIn("ioredis", js_info["imports"])
        self.assertIn("startServer", js_info["exports"])
        self.assertIn("infra:redis", js_info["infra"])

    def test_b4_defect_mining_formula_and_git_history(self):
        # 2 fixes (2*1.5=3.0) + 1 revert (1*3.0=3.0) = 6.0
        self.assertEqual(compute_defect_score(2, 1), 6.0)
        # Capped at 10.0
        self.assertEqual(compute_defect_score(6, 2), 10.0)

        defects = mine_git_defects_sync(self.demo_repo)
        self.assertTrue(len(defects) > 0)
        auth_entry = defects.get("auth.py") or defects.get("app/auth.py")
        self.assertIsNotNone(auth_entry)
        self.assertGreaterEqual(auth_entry["defect_score"], 5.0)

    def test_b5_blast_radius_bfs_on_three_graphs(self):
        # Graph 1: Linear chain A -> B -> C (A depends on B, B depends on C). Change in C impacts B (L1) and A (L2).
        edges1 = [
            CEdge(id="e1", source="A", target="B", type="import", weight=1.0),
            CEdge(id="e2", source="B", target="C", type="import", weight=1.0),
        ]
        imp1 = compute_blast_radius(edges1, ["C"])
        imp_map1 = {i.id: (i.depth, i.impact) for i in imp1}
        self.assertEqual(imp_map1["C"], (0, 1.0))
        self.assertEqual(imp_map1["B"], (1, 0.85))
        self.assertEqual(imp_map1["A"], (2, 0.72))

        # Graph 2: Star fan-out where R1, R2, R3 all depend on auth.py
        edges2 = [
            CEdge(id="e1", source="R1", target="auth", type="call", weight=1.0),
            CEdge(id="e2", source="R2", target="auth", type="call", weight=1.0),
            CEdge(id="e3", source="R3", target="auth", type="call", weight=1.0),
        ]
        imp2 = compute_blast_radius(edges2, ["auth"])
        self.assertEqual(len(imp2), 4)

        # Graph 3: Cycle handling (X <-> Y) terminates cleanly without infinite loop
        edges3 = [
            CEdge(id="e1", source="X", target="Y", type="import", weight=0.9),
            CEdge(id="e2", source="Y", target="X", type="import", weight=0.9),
        ]
        imp3 = compute_blast_radius(edges3, ["X"])
        self.assertEqual(len(imp3), 2)

    def test_b6_section_6_risk_engine_worked_example(self):
        # Worked example from Page 6 of Team Guide:
        # auth.py: +48 / -12 = 60 lines -> churn_n = 0.30.
        # Defect score 7 -> defect_n = 0.70.
        # Coverage 20% -> cover_n = 0.80.
        # Crown jewel impacted -> blast_n = 0.80.
        # r = 0.3*0.30 + 0.3*0.70 + 0.25*0.80 + 0.15*0.80 = 0.62 -> score = 62 + 15 (failing test) = 77 -> HOLD.
        churn_n, defect_n, cover_n, blast_n, r_node = compute_node_risk_factors(
            added=48, deleted=12, defect_score=7.0, coverage=0.20, blast_n=0.80
        )
        self.assertAlmostEqual(churn_n, 0.30)
        self.assertAlmostEqual(defect_n, 0.70)
        self.assertAlmostEqual(cover_n, 0.80)
        self.assertAlmostEqual(blast_n, 0.80)
        self.assertAlmostEqual(r_node, 0.62)

        score, verdict = compute_worked_example_score()
        self.assertEqual(score, 77)
        self.assertEqual(verdict, "HOLD")
        self.assertEqual(score_to_verdict(20), "GO")
        self.assertEqual(score_to_verdict(50), "CAUTION")

    def test_b8_backtest_lift(self):
        res = run_backtest(self.demo_repo)
        self.assertGreaterEqual(res["commits"], 20)
        self.assertGreater(res["lift"], 1.0)


if __name__ == "__main__":
    unittest.main()
