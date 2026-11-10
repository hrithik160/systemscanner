"""
Task B2 — Repository Loader (backend/app/analysis/loader.py)
Opens either a local folder path (validating existence, resolving paths, blocking traversal,
and copying into an isolated workspace) or clones a GitHub URL (`git clone --depth 300`).
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.config import WORKSPACES_DIR
from app.projects import PROJECT_REGISTRY, register_project


def open_local_or_github_sync(
    source: str,
    path_or_url: str,
    branch: Optional[str] = None,
) -> Tuple[str, Path]:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    cleaned = (path_or_url or "").strip()

    if source == "github" or cleaned.startswith(("https://", "http://", "git@")):
        if not cleaned.startswith(("https://", "http://", "git@")):
            raise ValueError("Invalid GitHub repository URL.")
        repo_slug = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            cleaned.rstrip("/").split("/")[-1].replace(".git", ""),
        ) or "gh_repo"
        pid = f"gh_{repo_slug}_{uuid.uuid4().hex[:6]}"
        dest_dir = (WORKSPACES_DIR / pid).resolve()
        if not str(dest_dir).startswith(str(WORKSPACES_DIR.resolve())):
            raise ValueError("Path traversal blocked.")

        cmd = ["git", "clone", "--depth", "300"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([cleaned, str(dest_dir)])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if res.returncode != 0 or not dest_dir.exists():
            raise RuntimeError((res.stderr or res.stdout or "git clone failed").strip())
        register_project(pid, dest_dir)
        return pid, dest_dir

    if not cleaned or cleaned == "demo":
        if "demo" in PROJECT_REGISTRY and PROJECT_REGISTRY["demo"].exists():
            return "demo", PROJECT_REGISTRY["demo"]
        raise FileNotFoundError("Demo repository is not initialized.")

    if cleaned in PROJECT_REGISTRY and PROJECT_REGISTRY[cleaned].exists():
        return cleaned, PROJECT_REGISTRY[cleaned]

    src_path = Path(cleaned).expanduser().resolve()
    if not src_path.exists() or not src_path.is_dir():
        raise FileNotFoundError(f"Local folder '{cleaned}' does not exist.")

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", src_path.name.lower()) or "project"
    pid = f"{safe_name}_{uuid.uuid4().hex[:6]}"
    dest_dir = (WORKSPACES_DIR / pid).resolve()
    shutil.copytree(
        src_path,
        dest_dir,
        ignore=shutil.ignore_patterns("node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build"),
    )
    register_project(pid, dest_dir)
    return pid, dest_dir


async def open_local_or_github(
    source: str,
    path_or_url: str,
    branch: Optional[str] = None,
) -> Tuple[str, Path]:
    return await asyncio.to_thread(open_local_or_github_sync, source, path_or_url, branch)
