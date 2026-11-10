"""
Task B7 / F15 — Release Report Generator (backend/app/analysis/report.py)
Generates Markdown and styled HTML release risk reports from `Graph`, `RiskResult`, `DiffResult`, and `MergeResult`.
"""
from __future__ import annotations

from app.api.routes_p3 import export_release_report_endpoint

__all__ = ["export_release_report_endpoint"]
