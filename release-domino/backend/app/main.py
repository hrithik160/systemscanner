"""
Unified FastAPI Entrypoint for Release Domino — Person 1 + Person 2 + Person 3 + Person 4
Mounts:
  - Person 1 LLM & Agent routes (`backend/app/api/routes_llm.py`)
  - Person 2 Docker, Tests & Git Ops routes (`backend/app/api/routes_p2.py`)
  - Person 3 Graph, Defect Mining, Blast Radius, Risk Engine & Report routes (`backend/app/api/routes_p3.py`)
  - Person 4 React Flow Frontend (`frontend/dist/`) served at `/` and `/ui`
"""
import asyncio
from contextlib import asynccontextmanager
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIST_DIR = REPO_ROOT / "frontend" / "dist"
for p in (str(BACKEND_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.api.routes_llm import router as llm_router
from app.api.routes_p2 import configure_p2_routes, register_project_watcher, router as p2_router
from app.api.routes_p3 import (
    build_project_graph_and_risk_sync,
    configure_p3_routes,
    record_test_run_state,
    router as p3_router,
)
from app.git_ops.watcher import watcher_manager

PROJECT_REGISTRY: Dict[str, Path] = {}
DEMO_REPO_PATH = REPO_ROOT / "demo" / "demo_shop_repo"
if DEMO_REPO_PATH.exists():
    PROJECT_REGISTRY["demo"] = DEMO_REPO_PATH

# In-memory fallback registry for unit tests when demo_shop_repo is not on disk
_MOCK_PROJECTS: dict[str, dict[str, Any]] = {
    "demo": {
        "project_id": "demo",
        "path": str(DEMO_REPO_PATH) if DEMO_REPO_PATH.exists() else ".",
        "nodes": [
            {"id": "auth.py", "path": "auth.py", "lang": "py", "is_crown_jewel": True, "deps": ["redis_cache"], "status": "changed"},
            {"id": "redis_cache.py", "path": "redis_cache.py", "lang": "py", "is_crown_jewel": False, "deps": ["redis"], "status": "normal"},
        ],
        "node_codes": {
            "auth.py": "import redis_cache\ndef authenticate(): return True",
            "redis_cache.py": "import redis\nclient = redis.Redis()",
        },
    }
}


def _extract_imports(code: str) -> List[str]:
    return sorted(set(re.findall(r"(?:^|\n)\s*(?:import|from)\s+([a-zA-Z0-9_]+)", code)))


def _detect_lang(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    if ext == ".py":
        return "py"
    if ext in (".ts", ".tsx"):
        return "ts"
    if ext in (".js", ".jsx"):
        return "js"
    return "other"


def get_project(pid: str) -> dict[str, Any] | None:
    """Helper used by Person 1 routes (`GET /api/architecture/{pid}`) to lookup project graph details."""
    repo_path = PROJECT_REGISTRY.get(pid)
    if repo_path and repo_path.exists():
        nodes: list[dict[str, Any]] = []
        node_codes: dict[str, str] = {}
        if pid in _MOCK_PROJECTS:
            for mn in _MOCK_PROJECTS[pid]["nodes"]:
                nodes.append(dict(mn))
            node_codes.update(_MOCK_PROJECTS[pid]["node_codes"])

        skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build", ".next"}
        for p in sorted(repo_path.rglob("*")):
            if not p.is_file() or any(s in p.parts for s in skip_dirs):
                continue
            if p.suffix.lower() not in (".py", ".js", ".jsx", ".ts", ".tsx"):
                continue
            rel = p.relative_to(repo_path).as_posix()
            try:
                code = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            deps = _extract_imports(code)
            lang = _detect_lang(rel)
            nodes.append({
                "id": rel,
                "path": rel,
                "lang": lang,
                "is_crown_jewel": "auth" in rel or "checkout" in rel or "main" in rel,
                "deps": deps,
                "status": "normal",
            })
            node_codes[rel] = code
            if p.name not in node_codes:
                node_codes[p.name] = code

        return {
            "project_id": pid,
            "path": str(repo_path),
            "nodes": nodes,
            "node_codes": node_codes,
        }

    return _MOCK_PROJECTS.get(pid)


def get_node_data(pid: str, nid: str) -> dict[str, Any] | None:
    """Helper used by Person 1 routes to lookup node code and dependencies from live sandbox projects."""
    clean_nid = nid.strip("/\\")
    repo_path = PROJECT_REGISTRY.get(pid)
    if repo_path and repo_path.exists():
        cand = repo_path / clean_nid
        if not (cand.exists() and cand.is_file()):
            skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
            for p in sorted(repo_path.rglob(Path(clean_nid).name), key=lambda x: len(x.parts)):
                if p.is_file() and not any(s in p.parts for s in skip_dirs):
                    cand = p
                    break
        if cand.exists() and cand.is_file():
            rel = cand.relative_to(repo_path).as_posix()
            code = cand.read_text(encoding="utf-8", errors="ignore")
            return {
                "code": code,
                "path": rel,
                "dependencies": _extract_imports(code),
                "lang": _detect_lang(rel),
            }

    proj = _MOCK_PROJECTS.get(pid)
    if proj:
        codes = proj.get("node_codes", {})
        if clean_nid in codes:
            return {
                "code": codes[clean_nid],
                "path": clean_nid,
                "dependencies": [d for n in proj.get("nodes", []) if n.get("id") == clean_nid for d in n.get("deps", [])],
                "lang": _detect_lang(clean_nid),
            }
    return None


EVENT_CLIENTS: Set[WebSocket] = set()
EVENT_LOG: list[dict] = []


async def broadcast_event(event_type: str, project_id: str, payload: dict) -> None:
    envelope = {
        "type": event_type,
        "project_id": project_id,
        "payload": payload,
        "ts": int(time.time() * 1000),
    }
    EVENT_LOG.append(envelope)

    # Sync Person 2 test/coverage results into Person 3's Risk Engine automatically
    if event_type == "test_run_finished" and isinstance(payload, dict):
        record_test_run_state(project_id, payload)
        repo_path = PROJECT_REGISTRY.get(project_id)
        if repo_path and repo_path.exists():
            try:
                _, risk = await asyncio.to_thread(build_project_graph_and_risk_sync, project_id, repo_path)
                risk_env = {
                    "type": "risk_updated",
                    "project_id": project_id,
                    "payload": risk.to_dict(),
                    "ts": int(time.time() * 1000),
                }
                EVENT_LOG.append(risk_env)
                for ws in list(EVENT_CLIENTS):
                    try:
                        await ws.send_json(risk_env)
                    except Exception:
                        pass
            except Exception:
                pass

    stale = set()
    for ws in list(EVENT_CLIENTS):
        try:
            await ws.send_json(envelope)
        except Exception:
            stale.add(ws)
    for ws in stale:
        EVENT_CLIENTS.discard(ws)


async def _on_watcher_reanalyze(pid: str, changed_files: List[str]) -> None:
    repo_path = PROJECT_REGISTRY.get(pid)
    if repo_path and repo_path.exists():
        try:
            graph, risk = await asyncio.to_thread(build_project_graph_and_risk_sync, pid, repo_path)
            await broadcast_event(
                "impact_computed",
                pid,
                {"changed_nodes": risk.changed_nodes, "impacted": [i.to_dict() for i in risk.impacted]},
            )
            await broadcast_event("risk_updated", pid, risk.to_dict())
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    loop = asyncio.get_running_loop()
    for pid, path in list(PROJECT_REGISTRY.items()):
        if path.exists():
            register_project_watcher(pid, path, loop=loop)
    yield
    watcher_manager.stop_all()


app = FastAPI(
    title="Release Domino — Full Stack (P1 LLM + P2 Docker/Git + P3 Graph/Risk + P4 React Flow UI)",
    description="AI-native visual release risk sandbox",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configure_p2_routes(PROJECT_REGISTRY, broadcast_event, on_reanalyze=_on_watcher_reanalyze)
configure_p3_routes(PROJECT_REGISTRY, broadcast_event)
app.include_router(llm_router)
app.include_router(p2_router)
app.include_router(p3_router)

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="frontend_assets")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "owner": "Person 1 (LLM) + Person 2 (Docker/Git) + Person 3 (Graph/Risk) + Person 4 (React Flow UI)",
        "registered_projects": {k: str(v) for k, v in PROJECT_REGISTRY.items()},
    }


@app.websocket("/ws/events")
async def ws_events_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    EVENT_CLIENTS.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        EVENT_CLIENTS.discard(ws)


@app.get("/demo-p2", response_class=HTMLResponse)
async def serve_legacy_sandbox_ui() -> HTMLResponse:
    ui_path = APP_DIR / "sandbox_ui.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Sandbox UI not found</h1>", status_code=404)


@app.get("/ui", response_class=HTMLResponse)
async def serve_react_flow_ui() -> HTMLResponse:
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return HTMLResponse(dist_index.read_text(encoding="utf-8"))
    ui_path = APP_DIR / "sandbox_ui.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>UI not found</h1>", status_code=404)


@app.get("/favicon.svg")
async def serve_favicon():
    fav = FRONTEND_DIST_DIR / "favicon.svg"
    if fav.exists():
        return FileResponse(str(fav), media_type="image/svg+xml")
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0f172a"/><circle cx="16" cy="16" r="9" fill="none" stroke="#ef4444" stroke-width="3"/><circle cx="16" cy="16" r="4" fill="#38bdf8"/></svg>'
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/")
async def root(request: Request):
    """
    Serves the compiled Person 4 React Flow UI (`frontend/dist/index.html`) when opened in a browser
    (`Accept: text/html`), and returns the Person 1 health-check JSON when called by API clients
    or TestClient (`test_live_api.py`).
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        dist_index = FRONTEND_DIST_DIR / "index.html"
        if dist_index.exists():
            return HTMLResponse(dist_index.read_text(encoding="utf-8"))
        ui_path = APP_DIR / "sandbox_ui.html"
        if ui_path.exists():
            return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return JSONResponse({
        "status": "ok",
        "service": "Release Domino Backend (Person 1 LLM Ready & Person 2 Docker Ready)",
    })
