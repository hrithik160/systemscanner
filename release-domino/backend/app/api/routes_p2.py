import base64
"""
Person 2 API & WebSocket Routes (backend/app/api/routes_p2.py)
Exposes the exact contract endpoints from Section 5 of the Team Guide plus
Sandbox Folder Upload, GitHub Clone, and Docker Image Management endpoints:
  - GET  /api/diff/{pid}
  - GET  /api/merge-check/{pid}
  - POST /api/tests/run
  - POST /api/project/{pid}/install-deps
  - GET  /api/docker/status
  - POST /api/docker/build-images
  - GET  /api/sandbox/projects
  - POST /api/sandbox/upload-folder
  - POST /api/sandbox/clone-github
  - WS   /ws/terminal/{pid}
"""
import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket
from pydantic import BaseModel

from app.git_ops.diff import compute_diff
from app.git_ops.merge_check import check_merge_conflicts
from app.git_ops.watcher import DebouncedRepoWatcher, watcher_manager
from app.runner.docker_runner import (
    ensure_runner_image_built_sync,
    get_docker_status_sync,
    install_project_dependencies,
)
from app.runner.terminal import detect_project_runtime, handle_terminal_websocket
from app.runner.tests import run_tests
from shared.models import DiffResult, MergeResult

logger = logging.getLogger("release_domino.api.routes_p2")
router = APIRouter()

_PROJECT_PATHS: Dict[str, Path] = {}
_EVENT_EMITTER: Optional[Callable[[str, str, dict], Awaitable[None]]] = None
_REANALYZE_CB: Optional[Callable[[str, List[str]], Awaitable[None]]] = None
SANDBOX_PROJECTS_ROOT = Path(tempfile.gettempdir()) / "rd_sandbox_projects"


def configure_p2_routes(
    project_paths: Dict[str, Path],
    emit_event: Callable[[str, str, dict], Awaitable[None]],
    on_reanalyze: Optional[Callable[[str, List[str]], Awaitable[None]]] = None,
) -> None:
    global _PROJECT_PATHS, _EVENT_EMITTER, _REANALYZE_CB
    _PROJECT_PATHS = project_paths
    _EVENT_EMITTER = emit_event
    _REANALYZE_CB = on_reanalyze


def register_project_watcher(
    pid: str,
    repo_path: Path,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> DebouncedRepoWatcher:
    """Registers `pid -> repo_path` and starts its 500ms debounced file watcher (Task D8)."""
    _PROJECT_PATHS[pid] = repo_path.resolve()
    return watcher_manager.start_watching(
        project_id=pid,
        repo_path=repo_path,
        emit_event=_emit,
        on_reanalyze=_REANALYZE_CB,
        loop=loop,
    )


def _get_repo_path(pid: str) -> Path:
    path = _PROJECT_PATHS.get(pid)
    if not path or not path.exists():
        cand = SANDBOX_PROJECTS_ROOT / pid
        if cand.exists() and cand.is_dir():
            _PROJECT_PATHS[pid] = cand.resolve()
            path = _PROJECT_PATHS[pid]
        else:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "PROJECT_NOT_FOUND", "message": f"Project '{pid}' not found"}},
            )
    try:
        loop = asyncio.get_running_loop()
        watcher_manager.start_watching(pid, path, _emit, _REANALYZE_CB, loop=loop)
    except RuntimeError:
        pass
    return path


async def _emit(event_type: str, pid: str, payload: dict) -> None:
    if _EVENT_EMITTER:
        await _EVENT_EMITTER(event_type, pid, payload)


def _build_and_emit_graph_risk_sync(pid: str, path: Path):
    try:
        from app.api.routes_p3 import build_project_graph_and_risk_sync
        return build_project_graph_and_risk_sync(pid, path)
    except Exception as exc:
        logger.warning(f"Could not build graph for {pid}: {exc}")
        return None, None


class TestRunRequest(BaseModel):
    pid: str
    node_ids: Optional[List[str]] = None
    test_code: Optional[str] = None
    lang: Optional[str] = None
    install_deps: bool = False
    strict_docker: bool = False
    keep_alive_sec: int = 0
    wait: bool = False


class InstallDepsRequest(BaseModel):
    mode: str = "py"
    force: bool = False


class BuildImagesRequest(BaseModel):
    langs: List[str] = ["py", "node"]


class UploadedFileItem(BaseModel):
    path: str
    content: str
    is_base64: bool = False


class UploadFolderRequest(BaseModel):
    project_name: str
    files: List[UploadedFileItem]


class CloneGithubRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = None


def _list_repo_files(repo_path: Path, limit: int = 60) -> List[str]:
    files: List[str] = []
    for p in sorted(repo_path.rglob("*")):
        if not p.is_file():
            continue
        if any(skip in p.parts for skip in (".git", "node_modules", ".venv", "__pycache__")):
            continue
        files.append(str(p.relative_to(repo_path)).replace("\\", "/"))
        if len(files) >= limit:
            break
    return files


def _ensure_git_initialized(dest: Path) -> None:
    if not (dest / ".git").exists():
        try:
            subprocess.run(["git", "init", "-b", "main"], cwd=str(dest), capture_output=True, check=False)
            subprocess.run(["git", "config", "user.name", "Release Domino Sandbox"], cwd=str(dest), capture_output=True, check=False)
            subprocess.run(["git", "config", "user.email", "sandbox@release-domino.local"], cwd=str(dest), capture_output=True, check=False)
            subprocess.run(["git", "add", "-A"], cwd=str(dest), capture_output=True, check=False)
            subprocess.run(["git", "commit", "-m", "chore: initial sandbox snapshot", "--allow-empty"], cwd=str(dest), capture_output=True, check=False)
        except Exception:
            pass


@router.get("/api/docker/status")
async def get_docker_status_endpoint() -> Dict[str, Any]:
    return await asyncio.to_thread(get_docker_status_sync)


@router.post("/api/docker/build-images")
async def build_docker_images_endpoint(req: BuildImagesRequest, bg: BackgroundTasks) -> Dict[str, Any]:
    langs = req.langs or ["py", "node"]

    def _build_worker():
        for l in langs:
            ensure_runner_image_built_sync(l, force=True)

    bg.add_task(_build_worker)
    return {
        "status": "building",
        "langs": langs,
        "message": f"Triggered Docker build for {langs}. Check /api/docker/status for completion.",
    }


@router.get("/api/sandbox/projects")
async def list_sandbox_projects() -> Dict[str, Any]:
    items = []
    for pid, path in _PROJECT_PATHS.items():
        if path.exists():
            files = await asyncio.to_thread(_list_repo_files, path, 60)
            rt = await asyncio.to_thread(detect_project_runtime, path)
            items.append({
                "pid": pid,
                "project_id": pid,
                "name": path.name,
                "stack": rt.get("stack", "Python"),
                "runtime": rt.get("stack", "py"),
                "path": str(path),
                "files": files,
                "file_count": len(files),
            })
    return {"projects": items}


@router.post("/api/sandbox/upload-folder")
async def upload_project_folder(req: UploadFolderRequest) -> Dict[str, Any]:
    if not req.files:
        raise HTTPException(status_code=400, detail="No files provided in uploaded folder.")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", req.project_name.strip().lower()).strip("-") or "folder"
    pid = f"{slug}_{uuid.uuid4().hex[:6]}"
    dest = SANDBOX_PROJECTS_ROOT / pid
    dest.mkdir(parents=True, exist_ok=True)

    def _write_all() -> List[str]:
        written = []
        for item in req.files:
            rel = item.path.replace("\\", "/").lstrip("/")
            parts = [p for p in rel.split("/") if p and p not in (".", "..")]
            if not parts:
                continue
            if len(parts) > 1 and parts[0].lower() == req.project_name.strip().lower():
                parts = parts[1:]
            clean_rel = "/".join(parts)
            target_f = dest / clean_rel
            target_f.parent.mkdir(parents=True, exist_ok=True)
            if item.is_base64:
                try:
                    raw_b64 = item.content.split(",", 1)[-1] if "," in item.content else item.content
                    target_f.write_bytes(base64.b64decode(raw_b64))
                except Exception:
                    pass
            else:
                target_f.write_text(item.content, encoding="utf-8", errors="ignore")
            written.append(clean_rel)
        _ensure_git_initialized(dest)
        return written

    written_files = await asyncio.to_thread(_write_all)
    register_project_watcher(pid, dest, loop=asyncio.get_running_loop())
    graph, risk = await asyncio.to_thread(_build_and_emit_graph_risk_sync, pid, dest)
    arch_dict = None
    if graph and risk:
        await _emit("graph_loaded", pid, graph.to_dict())
        await _emit("risk_updated", pid, risk.to_dict())
        try:
            from app.llm.arch import detect_architecture
            arch_res = await detect_architecture(
                nodes=[n.to_dict() for n in graph.nodes],
                project_path=dest,
            )
            arch_dict = arch_res.model_dump() if hasattr(arch_res, "model_dump") else arch_res.dict()
            await _emit("architecture_updated", pid, arch_dict)
        except Exception:
            pass
    return {
        "pid": pid,
        "project_id": pid,
        "name": req.project_name,
        "path": str(dest),
        "file_count": len(written_files),
        "files": written_files[:50],
        "graph": graph.to_dict() if graph else None,
        "risk": risk.to_dict() if risk else None,
        "architecture": arch_dict,
    }


@router.post("/api/sandbox/clone-github")
async def clone_github_repo(req: CloneGithubRequest) -> Dict[str, Any]:
    url = req.repo_url.strip()
    if not url.startswith(("https://github.com/", "http://github.com/", "git@github.com:")):
        raise HTTPException(status_code=400, detail="Please enter a valid GitHub repository URL (https://github.com/owner/repo).")

    repo_name = url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", repo_name.lower()).strip("-") or "gh-repo"
    pid = f"gh_{slug}_{uuid.uuid4().hex[:6]}"
    dest = SANDBOX_PROJECTS_ROOT / pid
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _clone() -> tuple[int, str, List[str]]:
        cmd = ["git", "clone", "--depth", "50"]
        if req.branch and req.branch.strip():
            cmd.extend(["-b", req.branch.strip()])
        cmd.extend([url, str(dest)])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=False)
            out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            if res.returncode != 0:
                return res.returncode, out, []
            return 0, out, _list_repo_files(dest, 60)
        except Exception as exc:
            return 1, str(exc), []

    code, clone_log, files = await asyncio.to_thread(_clone)
    if code != 0:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "GIT_CLONE_FAILED", "message": f"GitHub clone failed: {clone_log}"}},
        )

    register_project_watcher(pid, dest, loop=asyncio.get_running_loop())
    graph, risk = await asyncio.to_thread(_build_and_emit_graph_risk_sync, pid, dest)
    if graph and risk:
        await _emit("graph_loaded", pid, graph.to_dict())
        await _emit("risk_updated", pid, risk.to_dict())
    return {
        "pid": pid,
        "project_id": pid,
        "name": repo_name,
        "path": str(dest),
        "branch": req.branch,
        "file_count": len(files),
        "files": files[:50],
        "graph": graph.to_dict() if graph else None,
        "risk": risk.to_dict() if risk else None,
    }


@router.get("/api/diff/{pid}")
async def get_project_diff(pid: str) -> DiffResult:
    repo_path = _get_repo_path(pid)
    res = await compute_diff(repo_path)
    await _emit("diff_updated", pid, res.model_dump())
    return res


@router.get("/api/merge-check/{pid}")
async def get_project_merge_check(pid: str) -> MergeResult:
    repo_path = _get_repo_path(pid)
    res = await check_merge_conflicts(repo_path, base_branch="origin/main")
    await _emit("merge_checked", pid, res.model_dump())
    return res


@router.post("/api/tests/run")
async def run_tests_endpoint(req: TestRunRequest, bg: BackgroundTasks) -> Dict[str, Any]:
    repo_path = _get_repo_path(req.pid)

    if req.wait:
        result = await run_tests(
            pid=req.pid,
            repo_path=repo_path,
            node_ids=req.node_ids,
            test_code=req.test_code,
            lang=req.lang,
            emit_event=_emit,
            install_deps=req.install_deps,
            strict_docker=req.strict_docker,
            keep_alive_sec=req.keep_alive_sec,
        )
        d = result.model_dump()
        return {"result": d, **d}

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    async def _bg():
        await run_tests(
            pid=req.pid,
            repo_path=repo_path,
            node_ids=req.node_ids,
            test_code=req.test_code,
            lang=req.lang,
            emit_event=_emit,
            install_deps=req.install_deps,
            strict_docker=req.strict_docker,
            keep_alive_sec=req.keep_alive_sec,
            run_id=run_id,
        )

    bg.add_task(_bg)
    return {
        "run_id": run_id,
        "status": "queued",
        "message": f"Tests queued for project '{req.pid}'. Results will be broadcast to /ws/events.",
    }


@router.post("/api/project/{pid}/install-deps")
async def install_deps_endpoint(pid: str, req: InstallDepsRequest) -> Dict[str, Any]:
    repo_path = _get_repo_path(pid)
    code, out = await asyncio.to_thread(install_project_dependencies, repo_path, req.mode, req.force)
    return {
        "project_id": pid,
        "mode": req.mode,
        "exit_code": code,
        "success": code == 0,
        "output": out,
    }


@router.websocket("/ws/terminal/{pid}")
async def ws_terminal_endpoint(ws: WebSocket, pid: str) -> None:
    repo_path = _get_repo_path(pid)
    await handle_terminal_websocket(ws, pid, repo_path, emit_event=_emit)
