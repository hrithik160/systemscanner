"""
Task B3 — Dependency Graph Coordinator (backend/app/analysis/graph.py)
Re-exports `build_project_graph_and_risk_sync` so both `app.analysis.graph` and `app.api.routes_p3`
share the unified AST + Defect + Blast Radius + Risk Engine pipeline.
"""
from __future__ import annotations

from app.api.routes_p3 import build_project_graph_and_risk_sync

__all__ = ["build_project_graph_and_risk_sync"]
