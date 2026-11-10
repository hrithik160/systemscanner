"""
Task B4 — Git Defect History Miner (backend/app/analysis/defects.py)
Implements Section 6 Defect Mining rules:
  git log --since=180.days --name-only --pretty=format:%H|%s
A commit counts as a fix when its message matches (fix|bug|hotfix|patch) (case-insensitive),
and as a revert when it matches revert.
defect_score = min(10, 1.5*fixes_180d + 3*reverts_180d)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict

FIX_RE = re.compile(r"\b(fix|fixes|fixed|bug|hotfix|patch)\b", re.IGNORECASE)
REVERT_RE = re.compile(r"\brevert\b", re.IGNORECASE)


def compute_defect_score(fixes_180d: int, reverts_180d: int) -> float:
    return min(10.0, round(1.5 * fixes_180d + 3.0 * reverts_180d, 1))


def mine_git_defects_sync(repo_path: Path) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    if not (repo_path / ".git").exists():
        return stats
    try:
        res = subprocess.run(
            ["git", "log", "--since=180.days", "--name-only", "--pretty=format:COMMIT|%H|%s"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        out = res.stdout or ""
        if not out.strip():
            res = subprocess.run(
                ["git", "log", "-n", "100", "--name-only", "--pretty=format:COMMIT|%H|%s"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            out = res.stdout or ""
    except Exception:
        return stats

    current_msg = ""
    is_fix = False
    is_revert = False
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("COMMIT|"):
            parts = line.split("|", 2)
            current_msg = parts[2] if len(parts) > 2 else ""
            is_revert = bool(REVERT_RE.search(current_msg))
            is_fix = bool(FIX_RE.search(current_msg)) and not is_revert
        else:
            norm_path = line.replace("\\", "/")
            entry = stats.setdefault(
                norm_path,
                {"commits_180d": 0, "fixes_180d": 0, "reverts_180d": 0, "recent_messages": []},
            )
            entry["commits_180d"] += 1
            if is_fix:
                entry["fixes_180d"] += 1
            if is_revert:
                entry["reverts_180d"] += 1
            if current_msg and len(entry["recent_messages"]) < 5 and current_msg not in entry["recent_messages"]:
                entry["recent_messages"].append(current_msg)

    for entry in stats.values():
        entry["defect_score"] = compute_defect_score(entry["fixes_180d"], entry["reverts_180d"])
    return stats
