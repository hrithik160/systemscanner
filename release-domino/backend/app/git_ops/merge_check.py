"""
Task D7 — Merge-Conflict Radar vs origin/main (backend/app/git_ops/merge_check.py)
Runs `git fetch origin` (catching TimeoutExpired / OSError when offline) followed by
`git merge-tree --write-tree HEAD origin/main` (Git 2.38+) to detect conflicts without touching
the user's working tree, reads the conflicted blob directly from the written tree OID via
`git show <tree_oid>:<path>`, and extracts exact `<<<<<<< ... >>>>>>>` conflict marker line ranges.
"""
import asyncio
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

from shared.models import FileConflict, MergeResult

logger = logging.getLogger("release_domino.git_ops.merge_check")

HEX_OID_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _extract_conflict_ranges_from_blob(content: str) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    start_line: int | None = None
    for idx, line in enumerate(content.splitlines(), start=1):
        if line.startswith("<<<<<<<"):
            start_line = idx
        elif line.startswith(">>>>>>>") and start_line is not None:
            ranges.append((start_line, idx))
            start_line = None
    return ranges


def check_merge_conflicts_sync(repo_path: Path, base_branch: str = "origin/main") -> MergeResult:
    """
    Detects merge conflicts between HEAD and `base_branch` using `git merge-tree --write-tree`.
    Never modifies the working tree or index.
    """
    repo_path = repo_path.resolve()
    if not (repo_path / ".git").exists():
        return MergeResult(clean=True, base=base_branch, conflicts=[])

    # Attempt git fetch origin; safely catch TimeoutExpired or OSError when offline
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("git fetch origin skipped (offline or timed out): %s", exc)

    # Verify base_branch exists
    rev_check = subprocess.run(
        ["git", "rev-parse", "--verify", base_branch],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if rev_check.returncode != 0:
        return MergeResult(clean=True, base=base_branch, conflicts=[])

    # Run git merge-tree --write-tree HEAD origin/main (Git 2.38+)
    mt = subprocess.run(
        ["git", "merge-tree", "--write-tree", "HEAD", base_branch],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if mt.returncode == 0:
        return MergeResult(clean=True, base=base_branch, conflicts=[])

    out_lines = (mt.stdout or "").splitlines()
    tree_oid = out_lines[0].strip() if out_lines and HEX_OID_RE.match(out_lines[0].strip()) else ""

    # Parse conflicted file paths from merge-tree output
    conflicted_paths: set[str] = set()
    for line in (mt.stdout + "\n" + mt.stderr).splitlines():
        m = re.search(r"CONFLICT .*? in (.+)$", line.strip())
        if m:
            conflicted_paths.add(m.group(1).strip().replace("\\", "/"))

    # Extract exact conflict marker line ranges from the written tree OID via `git show <tree_oid>:<path>`
    exact_ranges: dict[str, List[Tuple[int, int]]] = {}
    if tree_oid:
        for cpath in conflicted_paths:
            show_res = subprocess.run(
                ["git", "show", f"{tree_oid}:{cpath}"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=False,
            )
            if show_res.returncode == 0 and show_res.stdout:
                ranges = _extract_conflict_ranges_from_blob(show_res.stdout)
                if ranges:
                    exact_ranges[cpath] = ranges

    # Fallback to classic 3-way merge-tree only if git < 2.38 or blob inspection produced no ranges
    if not exact_ranges:
        mb = subprocess.run(
            ["git", "merge-base", "HEAD", base_branch],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        merge_base = mb.stdout.strip() if mb.returncode == 0 else ""
        if merge_base:
            classic = subprocess.run(
                ["git", "merge-tree", merge_base, "HEAD", base_branch],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=False,
            )
            curr_file: str | None = None
            for line in classic.stdout.splitlines():
                if line.startswith("changed in both"):
                    curr_file = None
                elif line.strip().startswith(("base ", "our ", "their ")):
                    parts = line.split()
                    if len(parts) >= 4:
                        curr_file = parts[-1].strip().replace("\\", "/")
                        conflicted_paths.add(curr_file)
                elif line.startswith("@@ -") and curr_file:
                    m_hunk = re.search(r"\+(\d+)(?:,(\d+))?", line)
                    if m_hunk:
                        s_ln = int(m_hunk.group(1))
                        cnt = int(m_hunk.group(2)) if m_hunk.group(2) else 1
                        exact_ranges.setdefault(curr_file, []).append((s_ln, s_ln + max(0, cnt - 1)))

    conflicts: List[FileConflict] = []
    for cpath in sorted(conflicted_paths):
        lines = exact_ranges.get(cpath, [])
        conflicts.append(FileConflict(path=cpath, lines=lines))

    return MergeResult(
        clean=len(conflicts) == 0,
        base=base_branch,
        conflicts=conflicts,
    )


async def check_merge_conflicts(repo_path: Path, base_branch: str = "origin/main") -> MergeResult:
    """Async wrapper using asyncio.to_thread."""
    return await asyncio.to_thread(check_merge_conflicts_sync, repo_path, base_branch)
