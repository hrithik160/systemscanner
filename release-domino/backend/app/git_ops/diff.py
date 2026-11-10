"""
Task D6 — Git Diff Counter & Hunk Parser (backend/app/git_ops/diff.py)
Computes `git diff --numstat` and `git diff -U0` hunks vs HEAD (and vs origin/main fallback
if working tree has no uncommitted changes). Stages untracked files as intent-to-add (`git add -N`)
so newly created sandbox nodes appear in `DiffResult`. Uses `asyncio.to_thread` so the FastAPI
event loop is never blocked.
"""
import asyncio
import logging
import re
import subprocess
from pathlib import Path
from typing import List

from shared.models import DiffHunk, DiffResult, FileDiff

logger = logging.getLogger("release_domino.git_ops.diff")

HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _run_git_sync(args: List[str], cwd: Path) -> str:
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        return res.stdout or ""
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git %s failed in %s: %s", args, cwd, exc)
        return ""


def _stage_intent_to_add_untracked(repo_path: Path) -> None:
    """Marks untracked files with `git add -N` so sandbox files show up in `git diff` without committing them."""
    untracked_out = _run_git_sync(["ls-files", "--others", "--exclude-standard"], cwd=repo_path)
    untracked = [
        line.strip()
        for line in untracked_out.splitlines()
        if line.strip() and not line.strip().startswith(("rd_coverage_out", "rd_jest_out", ".coverage"))
    ]
    if untracked:
        _run_git_sync(["add", "-N", "--"] + untracked, cwd=repo_path)


def compute_diff_sync(repo_path: Path, base_ref: str = "HEAD") -> DiffResult:
    """
    Runs `git add -N` on untracked files, then `git diff --numstat` and `git diff -U0` against `base_ref`.
    If `base_ref == "HEAD"` and the working tree is clean, automatically falls back
    to `origin/main` (or `HEAD~1`) so committed feature-branch changes are still shown.
    """
    repo_path = repo_path.resolve()
    if not (repo_path / ".git").exists():
        logger.warning("Not a git repository: %s", repo_path)
        return DiffResult(files=[], total_added=0, total_deleted=0)

    _stage_intent_to_add_untracked(repo_path)

    numstat_out = _run_git_sync(["diff", "--numstat", base_ref], cwd=repo_path)
    effective_ref = base_ref

    if not numstat_out.strip() and base_ref == "HEAD":
        for fallback_ref in ("origin/main", "HEAD~1"):
            check = _run_git_sync(["diff", "--numstat", fallback_ref], cwd=repo_path)
            if check.strip():
                numstat_out = check
                effective_ref = fallback_ref
                break

    files_map: dict[str, FileDiff] = {}
    total_added = 0
    total_deleted = 0

    for line in numstat_out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add_s, del_s, fpath = parts
        added = int(add_s) if add_s.isdigit() else 0
        deleted = int(del_s) if del_s.isdigit() else 0
        norm_path = fpath.strip().replace("\\", "/")
        files_map[norm_path] = FileDiff(path=norm_path, added=added, deleted=deleted, hunks=[])
        total_added += added
        total_deleted += deleted

    # Parse -U0 hunks for exact changed line ranges
    u0_out = _run_git_sync(["diff", "-U0", effective_ref], cwd=repo_path)
    current_file: str | None = None
    for line in u0_out.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip().replace("\\", "/")
        elif line.startswith("@@ ") and current_file and current_file in files_map:
            m = HUNK_HEADER_RE.match(line)
            if m:
                start_line = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                end_line = start_line + max(0, count - 1)
                files_map[current_file].hunks.append(DiffHunk(start=start_line, end=end_line))

    return DiffResult(
        files=list(files_map.values()),
        total_added=total_added,
        total_deleted=total_deleted,
    )


async def compute_diff(repo_path: Path, base_ref: str = "HEAD") -> DiffResult:
    """Async wrapper around compute_diff_sync using asyncio.to_thread."""
    return await asyncio.to_thread(compute_diff_sync, repo_path, base_ref)
