"""
Task D9 — Test Impact Selection (backend/app/runner/impact.py)
Given changed file paths/node IDs and their dependents, discovers all test files in the repo
and selects only those matching by naming convention (`test_<module>.py`, `<module>.test.ts`)
or by direct import reference. Reports `(selected_test_files, total_test_files)`.
"""
import re
from pathlib import Path
from typing import Iterable, List, Tuple


def discover_all_test_files(repo_path: Path) -> List[str]:
    repo_path = repo_path.resolve()
    test_files: List[str] = []
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if any(skip in p.parts for skip in (".git", "node_modules", ".venv", "__pycache__")):
            continue
        name = p.name.lower()
        if (
            name.startswith("test_") and name.endswith(".py")
            or name.endswith("_test.py")
            or name.endswith(".test.ts")
            or name.endswith(".test.js")
            or name.endswith(".spec.ts")
            or name.endswith(".spec.js")
        ):
            rel = str(p.relative_to(repo_path)).replace("\\", "/")
            test_files.append(rel)
    return sorted(test_files)


def select_impacted_tests(
    repo_path: Path,
    affected_paths_or_ids: Iterable[str],
) -> Tuple[List[str], int]:
    """
    Returns `(selected_test_files, total_test_count)`.
    If `affected_paths_or_ids` is empty, returns all test files.
    """
    all_tests = discover_all_test_files(repo_path)
    total_count = len(all_tests)
    affected_list = [str(x).strip() for x in affected_paths_or_ids if x]
    if not affected_list or total_count == 0:
        return all_tests, total_count

    stems = set()
    for item in affected_list:
        clean = item.replace("\\", "/").split("/")[-1]
        stem = clean.rsplit(".", 1)[0].lower()
        if stem:
            stems.add(stem)

    selected = set()
    for rel_test in all_tests:
        t_name = rel_test.split("/")[-1].lower()
        # 1. Check naming convention match (e.g., cart.py -> test_cart.py)
        if any(
            t_name == f"test_{s}.py"
            or t_name == f"{s}_test.py"
            or t_name.startswith(f"{s}.test.")
            or t_name.startswith(f"{s}.spec.")
            for s in stems
        ):
            selected.add(rel_test)
            continue

        # 2. Check import statements inside the test file
        try:
            content = (repo_path / rel_test).read_text(encoding="utf-8", errors="ignore")
            for s in stems:
                if re.search(rf"\b(import\s+{re.escape(s)}|from\s+{re.escape(s)}\s+import)\b", content):
                    selected.add(rel_test)
                    break
        except OSError:
            pass

    return sorted(selected), total_count
