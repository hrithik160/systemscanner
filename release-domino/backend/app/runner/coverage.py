"""
Task D5 — Coverage Parser & Node Mapper (backend/app/runner/coverage.py)
Parses `pytest-cov` JSON (`rd_coverage_out.json`) or Jest `coverage/coverage-summary.json` into
a normalized `Dict[str, float]` where values are `0.0` to `1.0` per relative file path.
"""
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("release_domino.runner.coverage")


def _normalize_rel_path(file_key: str, workspace_root: Path) -> str:
    norm_key = str(file_key).replace("\\", "/")
    if norm_key.startswith("/workspace/"):
        return norm_key[len("/workspace/"):]
    try:
        return str(Path(norm_key).resolve().relative_to(workspace_root.resolve())).replace("\\", "/")
    except Exception:
        return norm_key.lstrip("./")


def parse_pytest_coverage_json(cov_json_path: Path, workspace_root: Path) -> Dict[str, float]:
    """
    Reads pytest-cov JSON report and returns `{ "cart.py": 1.0, "utils.py": 0.95 }` (0.0 to 1.0).
    """
    if not cov_json_path.exists():
        return {}
    try:
        raw = json.loads(cov_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse pytest coverage JSON %s: %s", cov_json_path, exc)
        return {}

    result: Dict[str, float] = {}
    files_section = raw.get("files") or {}
    for file_key, file_data in files_section.items():
        summary = file_data.get("summary") or {}
        pct = summary.get("percent_covered")
        if pct is None:
            continue
        rel = _normalize_rel_path(file_key, workspace_root)
        if rel.startswith("tests/") or "/test_" in f"/{rel}" or rel.startswith("_rd_"):
            continue
        result[rel] = round(min(1.0, max(0.0, float(pct) / 100.0)), 4)
    return result


def parse_jest_coverage_summary(cov_summary_path: Path, workspace_root: Path) -> Dict[str, float]:
    """
    Reads Jest's `coverage/coverage-summary.json` and returns normalized `{ "src/cart.js": 0.85 }` (0.0 to 1.0).
    """
    if not cov_summary_path.exists():
        return {}
    try:
        raw = json.loads(cov_summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse Jest coverage summary %s: %s", cov_summary_path, exc)
        return {}

    result: Dict[str, float] = {}
    for file_key, metrics in raw.items():
        if file_key == "total" or not isinstance(metrics, dict):
            continue
        lines_info = metrics.get("lines") or metrics.get("statements") or {}
        pct = lines_info.get("pct")
        if pct is None:
            continue
        rel = _normalize_rel_path(file_key, workspace_root)
        if ".test." in rel or ".spec." in rel or rel.startswith("tests/"):
            continue
        result[rel] = round(min(1.0, max(0.0, float(pct) / 100.0)), 4)
    return result
