"""
Person 3 In-Memory Project Registry (backend/app/projects.py)
Provides project path lookup, node code lookup, and runtime state storage
shared across Person 1 (LLM), Person 2 (Docker/Git), and Person 3 (Analysis/Risk).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import DEMO_REPO_PATH

PROJECT_REGISTRY: Dict[str, Path] = {}
if DEMO_REPO_PATH.exists():
    PROJECT_REGISTRY["demo"] = DEMO_REPO_PATH

MEASURED_COVERAGE: Dict[str, Dict[str, float]] = {}
FAILED_TEST_NODES: Dict[str, Set[str]] = {}
LAST_TEST_RUN: Dict[str, Dict[str, Any]] = {}
CROWN_OVERRIDES: Dict[str, Dict[str, bool]] = {}
SANDBOX_NODES: Dict[str, Dict[str, Dict[str, Any]]] = {}
SANDBOX_EDGES: Dict[str, List[Dict[str, Any]]] = {}
REMOVED_EDGES: Dict[str, Set[str]] = {}
BASELINE_SCORES: Dict[str, Tuple[float, str]] = {}
SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build", ".next", ".tox"}


def detect_lang(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    if ext == ".py":
        return "py"
    if ext in (".ts", ".tsx"):
        return "ts"
    if ext in (".js", ".jsx", ".mjs"):
        return "js"
    return "other"


def extract_imports_quick(code: str) -> List[str]:
    return sorted(set(re.findall(r"(?:^|\n)\s*(?:import|from)\s+([a-zA-Z0-9_]+)", code)))


def register_project(pid: str, path: Path) -> Path:
    resolved = path.resolve()
    PROJECT_REGISTRY[pid] = resolved
    return resolved


def get_project_path(pid: str) -> Optional[Path]:
    p = PROJECT_REGISTRY.get(pid)
    if p and p.exists():
        return p
    if pid == "demo" and DEMO_REPO_PATH.exists():
        PROJECT_REGISTRY["demo"] = DEMO_REPO_PATH
        return DEMO_REPO_PATH
    return None


def get_node_data(pid: str, nid: str) -> Optional[Dict[str, Any]]:
    """Used by Person 1 LLM endpoints to retrieve node source code & dependencies."""
    clean_nid = nid.strip("/\\")
    if clean_nid in SANDBOX_NODES.get(pid, {}):
        s_node = SANDBOX_NODES[pid][clean_nid]
        return {
            "code": s_node.get("code", ""),
            "path": clean_nid,
            "dependencies": s_node.get("imports", []),
            "lang": s_node.get("lang", "py"),
        }

    repo_path = get_project_path(pid)
    if repo_path and repo_path.exists():
        cand = repo_path / clean_nid
        if not (cand.exists() and cand.is_file()):
            for p in sorted(repo_path.rglob(Path(clean_nid).name), key=lambda x: len(x.parts)):
                if p.is_file() and not any(s in p.parts for s in SKIP_DIRS):
                    cand = p
                    break
        if cand.exists() and cand.is_file():
            rel = cand.relative_to(repo_path).as_posix()
            code = cand.read_text(encoding="utf-8", errors="ignore")
            return {
                "code": code,
                "path": rel,
                "dependencies": extract_imports_quick(code),
                "lang": detect_lang(rel),
            }
    return None
