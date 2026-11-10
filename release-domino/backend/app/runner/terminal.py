"""
Task D4 — Universal Multi-Stack Interactive Docker Terminal WebSocket Handler (backend/app/runner/terminal.py)
Supports:
  - Python Web & APIs: FastAPI, Flask, Django, Streamlit, Tornado, Bottle, HTTP servers, CLI scripts
  - Frontend JS/TS: React (Create React App), Vite (React/Vue/Svelte), Next.js, Vue CLI, Angular
  - Backend JS/TS: Node.js, Express, Fastify, Koa, NestJS
  - Full-Stack Monorepos: Python backend + built React/Vue/Vite frontend (served together)
  - Static Websites: HTML/CSS/JS folders (served via containerized HTTP server)
Automatically publishes container port 5000 to a free host port (e.g. `http://127.0.0.1:5050`),
intercepts localhost/port bindings inside Python and Node containers so they bind `0.0.0.0:5000`,
and emits `[LIVE_PREVIEW_URL] http://127.0.0.1:<port>` ONLY once port 5000 is actively listening
(including an automatic built-in HTTP portal if a CLI script or demo repo finishes without starting a server),
eliminating `ERR_EMPTY_RESPONSE`.
"""
import asyncio
import json
import logging
import shlex
import time
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.runner.docker_runner import (
    _find_manifest,
    build_frontend_dist,
    cleanup_sandbox,
    find_free_host_port,
    infer_python_requirements,
    install_project_dependencies,
    is_process_running,
    run_command,
    send_stdin_to_process,
    stop_project_container_sync,
)
from app.runner.tests import run_tests

logger = logging.getLogger("release_domino.runner.terminal")

ALLOWED_BINARIES = {
    "pytest", "python", "python3", "ls", "cat", "flake8", "ruff",
    "jest", "npm", "npx", "node", "uname", "id", "pwd", "uvicorn", "flask", "django-admin",
}

NODE_NET_WRAPPER = r'''// Universal Node.js / Express / Vite / React / Next.js container port & host interceptor
const net = require('net');
const http = require('http');
const fs = require('fs');
const path = require('path');

const hostPort = process.env.RD_HOST_PORT || '5050';
const inDocker = process.cwd().split(String.fromCharCode(92)).join('/').startsWith('/workspace');
const targetPort = inDocker ? 5000 : Number(hostPort);
const targetHost = inDocker ? '0.0.0.0' : '127.0.0.1';
let announced = false;
let mainPortBound = false;

function announceLiveUrl() {
  if (!announced) {
    announced = true;
    const url = 'http://127.0.0.1:' + hostPort;
    console.log('\\n[LIVE_PREVIEW_URL] ' + url);
    console.log('============================================================');
    console.log('>> Project is running live at: ' + url);
    console.log('============================================================\\n');
  }
}

// 1. Ignore EPERM on chmod inside non-root Windows Docker bind mounts
const origChmod = fs.chmod;
fs.chmod = function(p, mode, cb) {
  origChmod(p, mode, (err) => cb && cb(null));
};
const origChmodSync = fs.chmodSync;
fs.chmodSync = function(p, mode) {
  try { return origChmodSync(p, mode); } catch (e) { return; }
};

// 2. Force all Node HTTP/Express/Vite/Webpack servers to bind 0.0.0.0:5000 inside Docker
const origListen = net.Server.prototype.listen;
net.Server.prototype.listen = function(...args) {
  if (args.length > 0) {
    if (typeof args[0] === 'number' || (typeof args[0] === 'string' && /^\\d+$/.test(args[0]))) {
      const p = Number(args[0]);
      if (p > 0) {
        if (!mainPortBound) {
          args[0] = targetPort;
          mainPortBound = true;
        }
        if (typeof args[1] === 'string' && (args[1] === '127.0.0.1' || args[1] === 'localhost' || args[1] === '::1')) {
          args[1] = targetHost;
        } else if (typeof args[1] === 'function' || args[1] === undefined) {
          args.splice(1, 0, targetHost);
        }
      }
    } else if (args[0] && typeof args[0] === 'object' && 'port' in args[0]) {
      const opts = Object.assign({}, args[0]);
      if (Number(opts.port) > 0 && !mainPortBound) {
        opts.port = targetPort;
        mainPortBound = true;
      }
      if (!opts.host || opts.host === '127.0.0.1' || opts.host === 'localhost' || opts.host === '::1') {
        opts.host = targetHost;
      }
      args[0] = opts;
    }
  }
  this.once('listening', () => {
    const addr = this.address();
    if (addr && typeof addr === 'object' && addr.port === targetPort) {
      announceLiveUrl();
    }
  });
  return origListen.apply(this, args);
};

// 3. Track active executing module in workspace and emit [ACTIVE_NODE]
try {
  const Module = require('module');
  const origLoad = Module._load;
  const wsRoot = process.cwd().split(String.fromCharCode(92)).join('/');
  let lastActiveNode = '';
  Module._load = function(request, parent, isMain) {
    try {
      const resolved = Module._resolveFilename(request, parent, isMain);
      const norm = String(resolved).split(String.fromCharCode(92)).join('/');
      if (norm.startsWith(wsRoot) && !norm.includes('node_modules') && !norm.includes('_rd_node_wrapper')) {
        const rel = norm.slice(wsRoot.length).replace(/^\/+/, '');
        if (rel && rel !== lastActiveNode) {
          lastActiveNode = rel;
          console.log('[ACTIVE_NODE] ' + rel);
        }
      }
    } catch (e) {}
    return origLoad.apply(this, arguments);
  };
} catch (e) {}
// No beforeExit hook: prevents child processes (npm/vite workers) from hijacking port 5000.
'''

WEB_RUN_WRAPPER = '''import html, http.server, io, json, os, pathlib, runpy, socket, sys, traceback

target_script = sys.argv[1]
host_port = int(os.environ.get("RD_HOST_PORT", "5050"))
in_docker = pathlib.Path.cwd().as_posix().startswith("/workspace")
target_port = 5000 if in_docker else host_port
target_host = "0.0.0.0" if in_docker else "127.0.0.1"

# 1. Prevent PermissionError on os.chmod / Path.chmod inside uid 1000:1000 bind mounts
_orig_os_chmod = os.chmod
def _safe_os_chmod(path, mode, *args, **kwargs):
    try:
        return _orig_os_chmod(path, mode, *args, **kwargs)
    except (PermissionError, OSError):
        return None
os.chmod = _safe_os_chmod

_orig_path_chmod = pathlib.Path.chmod
def _safe_path_chmod(self, mode, *args, **kwargs):
    try:
        return _orig_path_chmod(self, mode, *args, **kwargs)
    except (PermissionError, OSError):
        return None
pathlib.Path.chmod = _safe_path_chmod

# 2. Ensure workspace and script directories are on sys.path (and chdir into nested project root if not a Python package)
script_dir = os.path.dirname(os.path.abspath(target_script))
ws_root = os.getcwd()
for p in (
    script_dir,
    os.path.join(ws_root, "backend/app"),
    os.path.join(ws_root, "backend"),
    os.path.join(ws_root, "src"),
    ws_root,
    "/workspace/backend/app",
    "/workspace/backend",
    "/workspace/src",
    "/workspace",
    ".",
):
    if p and os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)
if script_dir and os.path.isdir(script_dir) and script_dir != os.getcwd() and not os.path.isfile(os.path.join(script_dir, "__init__.py")):
    try:
        os.chdir(script_dir)
        target_script = os.path.basename(target_script)
    except Exception:
        pass

# Automatically load .env / .env.example if present in workspace or project dir
for env_name in (".env", ".env.local", ".env.development", ".env.example", ".env.sample"):
    for search_dir in (os.getcwd(), script_dir, "/workspace"):
        cand_env = os.path.join(search_dir, env_name)
        if os.path.isfile(cand_env):
            try:
                with open(cand_env, "r", encoding="utf-8", errors="ignore") as ef:
                    for eline in ef:
                        eline = eline.strip()
                        if eline and not eline.startswith("#") and "=" in eline:
                            k, v = eline.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'").strip('"')
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./dev_fallback.db"
if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = "release-domino-sandbox-secret-key-12345" 

# Tee stdout/stderr so if the script is a CLI/demo script that exits without starting a server,
# we can display its captured output on the fallback web portal!
_captured_out = []
class _TeeStream:
    def __init__(self, orig):
        self._orig = orig
    def write(self, s):
        if s:
            _captured_out.append(str(s))
        return self._orig.write(s)
    def flush(self):
        return self._orig.flush()
    def __getattr__(self, name):
        return getattr(self._orig, name)

sys.stdout = _TeeStream(sys.__stdout__)
sys.stderr = _TeeStream(sys.__stderr__)

# 3. Helper to announce live preview URL ONLY when a TCP server actually binds or listens
_announced = False
def _announce_live_url():
    global _announced
    if not _announced:
        _announced = True
        url = f"http://127.0.0.1:{host_port}"
        sys.__stdout__.write(f"\\n[LIVE_PREVIEW_URL] {url}\\n")
        sys.__stdout__.write("============================================================\\n")
        sys.__stdout__.write(f">> Project is running live at: {url}\\n")
        sys.__stdout__.write("============================================================\\n\\n")
        sys.__stdout__.flush()

# 4. Helper to mount compiled SPA (dist/build), rewrite hardcoded localhost API ports, and serve static assets
FRONTEND_ORIGIN_SHIM = """<script>
(function() {
  // Rewrite hardcoded localhost/127.0.0.1 API ports (e.g. :8000, :5000, :3000) to the active Docker container origin
  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function(input, init) {
      if (typeof input === string) {
        input = input.replace(/^https?:[/][/](localhost|127[.][0][.][0][.]1):[0-9]+/, window.location.origin);
      } else if (input && typeof input === object && input.url) {
        var newUrl = String(input.url).replace(/^https?:[/][/](localhost|127[.][0][.][0][.]1):[0-9]+/, window.location.origin);
        if (newUrl !== input.url) input = new Request(newUrl, input);
      }
      return origFetch.call(this, input, init);
    };
  }
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {
    if (typeof url === string) {
      arguments[1] = url.replace(/^https?:[/][/](localhost|127[.][0][.][0][.]1):[0-9]+/, window.location.origin);
    }
    return origOpen.apply(this, arguments);
  };
})();
</script>"""

def _prepare_spa_index_html(index_path, dist_dir=None):
    try:
        if os.path.isfile(index_path):
            raw_html = pathlib.Path(index_path).read_text(encoding="utf-8", errors="ignore")
        elif dist_dir and os.path.isdir(os.path.join(dist_dir, "assets")):
            assets_dir = pathlib.Path(dist_dir) / "assets"
            css_tags = "".join(f"<link rel='stylesheet' crossorigin href='/assets/{p.name}'>" for p in sorted(assets_dir.glob("*.css")))
            js_tags = "".join(f"<script type='module' crossorigin src='/assets/{p.name}'></script>" for p in sorted(assets_dir.glob("*.js")))
            raw_html = f"<!doctype html><html lang='en'><head><meta charset='UTF-8' /><meta name='viewport' content='width=device-width, initial-scale=1.0' /><title>App</title>{css_tags}{js_tags}</head><body><div id='root'></div></body></html>"
        else:
            return ""
        if "origFetch" not in raw_html:
            if "<head>" in raw_html:
                raw_html = raw_html.replace("<head>", "<head>" + FRONTEND_ORIGIN_SHIM, 1)
            else:
                raw_html = FRONTEND_ORIGIN_SHIM + raw_html
        return raw_html
    except Exception:
        return ""

def _mount_static_and_spa(app_obj):
    if app_obj is None or isinstance(app_obj, (dict, list, str, int, float, bool)):
        return
    if getattr(app_obj, "_rd_spa_mounted", False):
        return
    try:
        app_obj._rd_spa_mounted = True
        import mimetypes
        from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        mimetypes.add_type("application/javascript", ".js")
        mimetypes.add_type("application/javascript", ".mjs")
        mimetypes.add_type("text/css", ".css")
        mimetypes.add_type("image/svg+xml", ".svg")

        found_dist = None
        for cand in ("dist", "frontend/dist", "build", "frontend/build", "client/dist", "test_site", "static_site"):
            cand_abs = os.path.join(script_dir, cand) if not os.path.isdir(cand) and os.path.isdir(os.path.join(script_dir, cand)) else cand
            if os.path.isdir(cand_abs) and (os.path.isfile(os.path.join(cand_abs, "index.html")) or os.path.isdir(os.path.join(cand_abs, "assets"))):
                found_dist = os.path.abspath(cand_abs)
                break

        if found_dist:
            index_file = os.path.join(found_dist, "index.html")
            patched_html = _prepare_spa_index_html(index_file, dist_dir=found_dist)
            print(f"[Container Runner] Serving compiled SPA frontend from: {found_dist}", flush=True)
            no_cache_hdrs = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}

            class _SpaPreMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    req_path = request.url.path
                    if request.method in ("GET", "HEAD"):
                        # 1. Serve compiled dist/index.html on / or /index.html (overriding uncompiled root index.html!)
                        if req_path in ("/", "/index.html") and patched_html:
                            return HTMLResponse(patched_html, headers=no_cache_hdrs)
                        # 2. Serve any static asset in dist/ (/assets/*, images, icons, CSS, JS) directly!
                        rel = req_path.lstrip("/")
                        if rel and ".." not in rel:
                            candidate_file = os.path.join(found_dist, rel)
                            if os.path.isfile(candidate_file):
                                media_type, _ = mimetypes.guess_type(candidate_file)
                                return FileResponse(candidate_file, media_type=media_type)
                    response = await call_next(request)
                    # 3. SPA client-side route fallback: if GET html navigation returns 404, serve dist/index.html
                    if (
                        request.method == "GET"
                        and response.status_code == 404
                        and patched_html
                        and not req_path.startswith(("/api", "/docs", "/redoc", "/openapi.json"))
                        and "text/html" in request.headers.get("accept", "")
                    ):
                        return HTMLResponse(patched_html, headers=no_cache_hdrs)
                    return response

            app_obj.add_middleware(_SpaPreMiddleware)
            return

        # If no compiled dist/ folder exists, check for standalone static HTML (excluding all uncompiled templates with id="root"/TSX/JSX)
        found_static_html = None
        for html_cand in ("index.html", "frontend/index.html", "public/index.html", "templates/index.html"):
            if os.path.isfile(html_cand):
                raw_h = pathlib.Path(html_cand).read_text(encoding="utf-8", errors="ignore")
                is_uncompiled = (
                    "/src/" in raw_h
                    or "src/main" in raw_h
                    or "src/index" in raw_h
                    or 'id="root"' in raw_h
                    or "id='root'" in raw_h
                    or 'id="app"' in raw_h
                    or ".tsx" in raw_h
                    or ".jsx" in raw_h
                )
                if is_uncompiled and not os.path.isdir("assets"):
                    continue
                found_static_html = _prepare_spa_index_html(os.path.abspath(html_cand))
                break

        routes = getattr(app_obj, "routes", [])
        has_root = any(getattr(r, "path", None) == "/" for r in routes)
        if not has_root:
            if found_static_html:
                @app_obj.get("/", include_in_schema=False)
                async def _serve_root_file():
                    return HTMLResponse(found_static_html)
            else:
                @app_obj.get("/", include_in_schema=False)
                async def _serve_api_portal():
                    # If this app defines Swagger docs at /docs, redirect root to /docs!
                    return RedirectResponse(url="/docs")
    except Exception:
        pass

print(f"[Container Runner] Launching entrypoint: {target_script} (target={target_host}:{target_port})...", flush=True)

# 4b. Smart builtins.open & StaticFiles relative-path resolver for nested backend/main.py projects
import builtins
_orig_open = builtins.open
def _smart_open(file, *args, **kwargs):
    try:
        return _orig_open(file, *args, **kwargs)
    except FileNotFoundError:
        if isinstance(file, (str, pathlib.Path)) and not os.path.isabs(str(file)):
            alt = os.path.join(script_dir, str(file))
            if os.path.exists(alt):
                return _orig_open(alt, *args, **kwargs)
        raise
builtins.open = _smart_open

# 4c. Interactive stdin input() hook so CLI programs flush prompts immediately and wait for terminal input
_orig_input = builtins.input
def _rd_interactive_input(prompt=""):
    if prompt:
        sys.__stdout__.write(str(prompt))
        sys.__stdout__.flush()
    if os.environ.get("RD_INTERACTIVE_RUN") == "1":
        sys.__stdout__.write(chr(10) + "[WAITING_FOR_INPUT]" + chr(10))
        sys.__stdout__.flush()
    line = sys.stdin.readline()
    if not line:
        return ""
    return line.rstrip(chr(13) + chr(10))
builtins.input = _rd_interactive_input

# 4d. Real-time execution node tracker ([ACTIVE_NODE]) so the UI highlights active nodes in blue
import time as _rd_time
_ws_abs_root = os.path.abspath(ws_root)
_last_emitted_node = {}
_THROTTLE_SECONDS = 0.15

def _emit_active_node(rel_p):
    clean_p = str(rel_p).replace(chr(92), "/").lstrip("./")
    if not clean_p or clean_p.startswith("_rd_") or "site-packages" in clean_p or ".venv" in clean_p or clean_p.startswith(".."):
        return
    now_t = _rd_time.time()
    if (now_t - _last_emitted_node.get(clean_p, 0.0)) >= _THROTTLE_SECONDS:
        _last_emitted_node[clean_p] = now_t
        if os.environ.get("RD_INTERACTIVE_RUN") == "1":
            sys.__stdout__.write("[ACTIVE_NODE] " + clean_p + chr(10))
            sys.__stdout__.flush()

if os.environ.get("RD_INTERACTIVE_RUN") == "1":
    _emit_active_node(target_script)
    if sys.version_info >= (3, 12) and hasattr(sys, "monitoring"):
        try:
            _TOOL_ID = sys.monitoring.PROFILER_ID
            sys.monitoring.use_tool_id(_TOOL_ID, "rd_active_node_tracer")
            def _on_py_start(code, instruction_offset):
                co_f = os.path.abspath(code.co_filename)
                if co_f.startswith(_ws_abs_root):
                    rel_f = os.path.relpath(co_f, _ws_abs_root).replace(chr(92), "/")
                    _emit_active_node(rel_f)
            sys.monitoring.register_callback(_TOOL_ID, sys.monitoring.events.PY_START, _on_py_start)
            sys.monitoring.set_events(_TOOL_ID, sys.monitoring.events.PY_START)
        except Exception:
            pass
    else:
        def _rd_profile_tracer(frame, event, arg):
            if event == "call":
                try:
                    co_f = os.path.abspath(frame.f_code.co_filename)
                    if co_f.startswith(_ws_abs_root):
                        rel_f = os.path.relpath(co_f, _ws_abs_root).replace(chr(92), "/")
                        _emit_active_node(rel_f)
                except Exception:
                    pass
        sys.setprofile(_rd_profile_tracer)


try:
    import starlette.staticfiles
    _orig_sf_init = starlette.staticfiles.StaticFiles.__init__
    def _patched_sf_init(self, *args, **kwargs):
        d = kwargs.get("directory")
        if d and isinstance(d, (str, pathlib.Path)) and not os.path.isdir(str(d)):
            alt_d = os.path.join(script_dir, str(d))
            if os.path.isdir(alt_d):
                kwargs["directory"] = alt_d
            else:
                try:
                    os.makedirs(str(d), exist_ok=True)
                except Exception:
                    kwargs["check_dir"] = False
        return _orig_sf_init(self, *args, **kwargs)
    starlette.staticfiles.StaticFiles.__init__ = _patched_sf_init
except Exception:
    pass

# 5. Track FastAPI instances and patch uvicorn.run / uvicorn.Config so ANY uvicorn launch (even string "main:app") mounts SPA and binds 0.0.0.0:5000
_created_fastapi_apps = []
try:
    import fastapi
    _orig_fastapi_init = fastapi.FastAPI.__init__
    def _patched_fastapi_init(self, *args, **kwargs):
        _orig_fastapi_init(self, *args, **kwargs)
        _created_fastapi_apps.append(self)
    fastapi.FastAPI.__init__ = _patched_fastapi_init
except Exception:
    pass

try:
    import uvicorn
    _orig_uvicorn_run = uvicorn.run
    def _patched_uvicorn_run(app, *args, **kwargs):
        if isinstance(app, str) and _created_fastapi_apps:
            app = _created_fastapi_apps[-1]
        for fa in _created_fastapi_apps:
            _mount_static_and_spa(fa)
        if not isinstance(app, str):
            _mount_static_and_spa(app)
        kwargs["host"] = target_host
        kwargs["port"] = target_port
        kwargs["reload"] = False
        kwargs.pop("workers", None)
        return _orig_uvicorn_run(app, *args, **kwargs)
    uvicorn.run = _patched_uvicorn_run

    _orig_uvicorn_config_init = uvicorn.Config.__init__
    def _patched_uvicorn_config_init(self, app, *args, **kwargs):
        if isinstance(app, str) and _created_fastapi_apps:
            app = _created_fastapi_apps[-1]
        for fa in _created_fastapi_apps:
            _mount_static_and_spa(fa)
        if not isinstance(app, str):
            _mount_static_and_spa(app)
        kwargs["host"] = target_host
        kwargs["port"] = target_port
        kwargs["reload"] = False
        kwargs.pop("workers", None)
        return _orig_uvicorn_config_init(self, app, *args, **kwargs)
    uvicorn.Config.__init__ = _patched_uvicorn_config_init
except Exception:
    pass

# 6. Patch Flask.run so Flask apps bind to 0.0.0.0:5000 inside Docker without reloader fork
try:
    import flask
    _orig_flask_run = flask.Flask.run
    def _patched_flask_run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        options["use_reloader"] = False
        return _orig_flask_run(self, host=target_host, port=target_port, debug=debug, load_dotenv=load_dotenv, **options)
    flask.Flask.run = _patched_flask_run
except Exception:
    pass

# 7. Low-level TCP socket.socket.bind & listen hook: ONLY intercepts SOCK_STREAM (TCP) server sockets!
_orig_bind = socket.socket.bind
_orig_listen = socket.socket.listen
_main_bound_port = None

def _patched_bind(self, address):
    global _main_bound_port
    if getattr(self, "type", None) == socket.SOCK_STREAM and isinstance(address, tuple) and len(address) == 2:
        host, port = address
        if port > 0:
            if _main_bound_port is None or port == _main_bound_port:
                _main_bound_port = port
                address = (target_host, target_port)
            elif host in ("127.0.0.1", "localhost", "0.0.0.0", ""):
                address = (target_host, port)
    return _orig_bind(self, address)

def _patched_listen(self, *args, **kwargs):
    res = _orig_listen(self, *args, **kwargs)
    try:
        addr = self.getsockname()
        if isinstance(addr, tuple) and len(addr) >= 2 and addr[1] == target_port:
            _announce_live_url()
    except Exception:
        pass
    return res

socket.socket.bind = _patched_bind
socket.socket.listen = _patched_listen

# 8. Function to launch app objects if not already started
def _launch_app_object(app_obj):
    if app_obj is None or isinstance(app_obj, (dict, list, str, int, float, bool)):
        return False
    if hasattr(app_obj, "wsgi_app") and callable(getattr(app_obj, "run", None)):
        app_obj.run(host=target_host, port=target_port)
        return True
    if hasattr(app_obj, "router") or hasattr(app_obj, "routes") or type(app_obj).__name__ in ("FastAPI", "Starlette"):
        _mount_static_and_spa(app_obj)
        import uvicorn
        uvicorn.run(app_obj, host=target_host, port=target_port)
        return True
    return False

# 9. Built-in Fallback HTTP Portal when a CLI/demo script finishes or crashes without starting its own web server
def _serve_fallback_portal(mod_globals, error_tb=None):
    # If an index.html exists in the workspace, serve it or offer a tab to view it
    files_list = sorted(
        p.relative_to(".").as_posix()
        for p in pathlib.Path(".").rglob("*")
        if p.is_file() and not any(x in p.parts for x in (".git", "__pycache__", "node_modules", ".venv"))
    )[:60]
    out_text = "".join(_captured_out).strip() or "(No stdout output produced)"
    routes_info = ""
    if isinstance(mod_globals, dict) and callable(mod_globals.get("create_app")):
        try:
            res = mod_globals["create_app"]()
            routes_info = f"<div class=\\"card\\"><h3>Discovered App Config (<code>create_app()</code>)</h3><pre>{html.escape(json.dumps(res, indent=2))}</pre></div>"
        except Exception:
            pass

    status_badge = (
        "<span style=\\"background:#dc2626;color:white;padding:4px 10px;border-radius:999px;font-size:12px;\\">Script Raised Exception</span>"
        if error_tb else
        "<span style=\\"background:#10b981;color:#042f2e;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;\\">Container Active (UID 1000:1000)</span>"
    )
    err_section = f"<div class=\\"card\\" style=\\"border-color:#ef4444;\\"><h3 style=\\"color:#f87171;\\">Startup Exception Traceback</h3><pre style=\\"color:#fca5a5;\\">{html.escape(error_tb)}</pre></div>" if error_tb else ""

    page_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Release Domino — Live Container Portal ({html.escape(target_script)})</title>
  <style>
    body {{ background:#0b0f19; color:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; margin:0; padding:28px; }}
    .hdr {{ display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #374151; padding-bottom:16px; margin-bottom:20px; }}
    .card {{ background:#111827; border:1px solid #374151; border-radius:8px; padding:16px; margin-bottom:16px; }}
    h2 {{ margin:0; font-size:20px; }}
    h3 {{ margin:0 0 10px 0; font-size:14px; color:#9ca3af; text-transform:uppercase; letter-spacing:0.04em; }}
    pre {{ background:#070a12; border:1px solid #1f2937; padding:12px; border-radius:6px; overflow-x:auto; font-family:Consolas,monospace; font-size:13px; color:#34d399; margin:0; white-space:pre-wrap; }}
    .grid {{ display:grid; grid-template-columns: 2fr 1fr; gap:16px; }}
    ul {{ margin:0; padding-left:18px; font-family:Consolas,monospace; font-size:12.5px; color:#d1d5db; line-height:1.6; }}
  </style>
</head>
<body>
  <div class="hdr">
    <h2>🐳 Release Domino — Live Docker Container Portal (<code>/workspace/{html.escape(target_script)}</code>)</h2>
    {status_badge}
  </div>
  {err_section}
  <div class="grid">
    <div>
      <div class="card">
        <h3>Container Console Output (stdout / stderr)</h3>
        <pre>{html.escape(out_text)}</pre>
      </div>
      {routes_info}
    </div>
    <div class="card">
      <h3>Mounted Container Files ({len(files_list)})</h3>
      <ul>{"".join(f"<li>{html.escape(f)}</li>" for f in files_list)}</ul>
    </div>
  </div>
</body>
</html>"""

    class _PortalHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = page_html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()
        def log_message(self, fmt, *args):
            pass

    srv = http.server.ThreadingHTTPServer((target_host, target_port), _PortalHandler)
    srv.serve_forever()

# 10. Handle Django manage.py runserver
if os.path.basename(target_script) == "manage.py":
    sys.argv = [target_script, "runserver", f"{target_host}:{target_port}", "--noreload"]
else:
    sys.argv = [target_script]

_PIP_PKG_MAP = {
    "dotenv": "python-dotenv",
    "jose": "python-jose[cryptography]",
    "jwt": "PyJWT",
    "yaml": "pyyaml",
    "cv2": "opencv-python-headless",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "psycopg2": "psycopg2-binary",
    "pydantic_settings": "pydantic-settings",
    "email_validator": "email-validator",
    "multipart": "python-multipart",
    "flask_cors": "flask-cors",
    "flask_sqlalchemy": "flask-sqlalchemy",
    "flask_login": "flask-login",
}

def _run_with_auto_heal(script_path):
    import subprocess, tempfile
    auto_deps = os.path.join(tempfile.gettempdir(), "rd_auto_py_deps")
    if os.path.isdir(auto_deps) and auto_deps not in sys.path:
        sys.path.insert(0, auto_deps)
    abs_sp = os.path.abspath(script_path)
    sp_dir = os.path.dirname(abs_sp)
    if sp_dir and sp_dir not in sys.path:
        sys.path.insert(0, sp_dir)

    for _attempt in range(4):
        try:
            return runpy.run_path(script_path, run_name="__main__")
        except ImportError as ie:
            if "attempted relative import with no known parent package" in str(ie):
                # 1. Try running as package module
                parent_dir = os.path.dirname(sp_dir)
                pkg_name = os.path.basename(sp_dir)
                mod_name = os.path.splitext(os.path.basename(abs_sp))[0]
                if parent_dir and parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                try:
                    return runpy.run_module(f"{pkg_name}.{mod_name}", run_name="__main__")
                except Exception:
                    pass

                # 2. Rewrite top-level relative imports `from xxx import` -> `from xxx import`
                try:
                    src = open(abs_sp, "r", encoding="utf-8", errors="ignore").read()
                    healed = re.sub(r"\bfrom\s+\.([a-zA-Z0-9_]+)\s+import\b", r"from \1 import", src)
                    if healed != src:
                        code_obj = compile(healed, abs_sp, "exec")
                        globs = {"__name__": "__main__", "__file__": abs_sp}
                        exec(code_obj, globs)
                        return globs
                except Exception:
                    raise
            raise
        except ModuleNotFoundError as mnf:
            mod_name = (getattr(mnf, "name", "") or "").split(".")[0]
            if not mod_name or mod_name in ("app", "backend", "src", "main", "config", "models", "routes", "database", "schemas"):
                raise
            pkg = _PIP_PKG_MAP.get(mod_name, mod_name.replace("_", "-"))
            print(f"[Sandbox Auto-Healer] Missing Python package '{mod_name}' -> installing '{pkg}'...", flush=True)
            os.makedirs(auto_deps, exist_ok=True)
            if auto_deps not in sys.path:
                sys.path.insert(0, auto_deps)
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--prefer-binary", "--target", auto_deps, pkg],
                capture_output=True, text=True, timeout=90, check=False
            )
            if res.returncode != 0:
                raise
    return runpy.run_path(script_path, run_name="__main__")

mod_globals = {}
error_trace = None
try:
    mod_globals = _run_with_auto_heal(target_script)
    if not _announced:
        candidate_app = mod_globals.get("app") or mod_globals.get("application") or mod_globals.get("api")
        if not _launch_app_object(candidate_app):
            for follow_up in ("backend/main.py", "backend/app/main.py", "main.py", "app.py", "server.py"):
                if follow_up != target_script and os.path.exists(follow_up):
                    f_dir = os.path.dirname(os.path.abspath(follow_up))
                    if f_dir and f_dir not in sys.path:
                        sys.path.insert(0, f_dir)
                    print(f"[Sandbox Runner] Launching application entrypoint: {follow_up}...", flush=True)
                    sub_globals = runpy.run_path(follow_up, run_name="__main__")
                    sub_app = sub_globals.get("app") or sub_globals.get("application") or sub_globals.get("api")
                    if _launch_app_object(sub_app):
                        break
except Exception:
    full_tb = traceback.format_exc()
    tb_lines = full_tb.splitlines()
    filtered = []
    skip = False
    for line in tb_lines:
        if "_rd_web_wrapper.py" in line or "<frozen runpy>" in line:
            skip = True
            continue
        if skip and line.startswith("    "):
            continue
        skip = False
        filtered.append(line)
    clean_tb = chr(10).join(filtered)
    error_trace = clean_tb or full_tb

    sys.__stderr__.write(chr(10) + "=" * 60 + chr(10))
    sys.__stderr__.write(f">> [Container Runner] Application '{target_script}' raised an exception during startup:" + chr(10) + chr(10))
    sys.__stderr__.write(error_trace + chr(10))
    sys.__stderr__.write("=" * 60 + chr(10) + chr(10))
    sys.__stderr__.flush()

# If the script finished (or raised an error) without keeping an HTTP server open,
# and we are running in interactive container mode (RD_INTERACTIVE_RUN=1), start the fallback web portal!
if not _announced and os.environ.get("RD_INTERACTIVE_RUN") == "1":
    _announce_live_url()
    _serve_fallback_portal(mod_globals, error_tb=error_trace)
elif error_trace:
    sys.exit(1)
'''


def detect_project_runtime(repo_path: Path) -> Dict[str, Any]:
    """
    Universal multi-stack detector. Inspects `repo_path` (including nested GitHub folders)
    and returns runtime configuration for React/Vite, CRA, Next.js, Node/Express,
    FastAPI, Flask, Django, Streamlit, Full-Stack Monorepos, and Static HTML sites.
    """
    has_compiled_spa = any(
        (repo_path / d).exists()
        for d in (
            "dist/index.html",
            "dist/assets",
            "frontend/dist/index.html",
            "frontend/dist/assets",
            "build/index.html",
            "frontend/build/index.html",
            "client/dist/index.html",
        )
    ) or any(
        p.parent.name in ("dist", "build")
        and not any(s in p.parts for s in (".git", "node_modules", ".venv", "venv", "__pycache__"))
        for p in repo_path.rglob("index.html")
    )

    py_candidates = (
        "main.py",
        "app.py",
        "run.py",
        "server.py",
        "index.py",
        "manage.py",
        "backend/main.py",
        "backend/app/main.py",
        "backend/app.py",
        "backend/server.py",
        "app/main.py",
        "src/main.py",
        "src/app.py",
    )
    found_py: Optional[str] = None
    for cand in py_candidates:
        if (repo_path / cand).exists():
            found_py = cand
            break

    if not found_py:
        for sub_py in sorted(repo_path.rglob("*.py"), key=lambda p: len(p.parts)):
            if any(skip in sub_py.parts for skip in (".git", "node_modules", ".venv", "venv", "__pycache__", "tests", "test")):
                continue
            if sub_py.name in ("main.py", "app.py", "server.py", "manage.py", "run.py") and len(sub_py.relative_to(repo_path).parts) <= 3:
                found_py = sub_py.relative_to(repo_path).as_posix()
                break

    is_py_web_server = False
    if found_py and (repo_path / found_py).is_file():
        py_src = (repo_path / found_py).read_text(encoding="utf-8", errors="ignore")
        if any(w in py_src for w in ("FastAPI", "fastapi", "Flask", "flask", "django", "streamlit", "tornado", "aiohttp", "uvicorn", "http.server")) or found_py.endswith("manage.py"):
            is_py_web_server = True

    node_manifest = _find_manifest(repo_path, "node")
    prefer_node = bool(node_manifest is not None and (found_py is None or not is_py_web_server))

    if node_manifest is not None and prefer_node:
        pkg_rel_dir = str(node_manifest.parent.relative_to(repo_path)).replace("\\", "/")
        if pkg_rel_dir == ".":
            pkg_rel_dir = ""
        try:
            pkg_data = json.loads(node_manifest.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pkg_data = {}
        scripts = pkg_data.get("scripts") or {}
        deps = {}
        deps.update(pkg_data.get("dependencies") or {})
        deps.update(pkg_data.get("devDependencies") or {})

        cd_prefix = f"cd /workspace/{pkg_rel_dir} && " if pkg_rel_dir else ""
        preload = 'NODE_OPTIONS="--require /workspace/_rd_node_wrapper.cjs"'

        pkg_dir = node_manifest.parent
        has_vite_files = (
            "vite" in deps
            or "vite" in str(scripts.get("dev", ""))
            or (pkg_dir / "vite.config.js").exists()
            or (pkg_dir / "vite.config.ts").exists()
            or (pkg_dir / "vite.config.mjs").exists()
            or (
                (pkg_dir / "index.html").is_file()
                and any(
                    t in (pkg_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
                    for t in ("/src/main.", "/src/index.", "./src/main.", "./src/index.")
                )
            )
        )

        if has_vite_files:
            script_name = "dev" if "dev" in scripts else "start"
            return {
                "stack": "React / Vite",
                "mode": "node",
                "cmd_args": [
                    "sh",
                    "-c",
                    f"{cd_prefix}if [ -x ./node_modules/.bin/vite ]; then {preload} ./node_modules/.bin/vite --host 0.0.0.0 --port 5000; else {preload} npm run {script_name} -- --host 0.0.0.0 --port 5000; fi",
                ],
                "use_py_wrapper": False,
                "use_node_wrapper": True,
                "node_pkg_rel_dir": pkg_rel_dir,
                "is_web": True,
            }
        if "next" in deps:
            script_name = "dev" if "dev" in scripts else "start"
            return {
                "stack": "Next.js",
                "mode": "node",
                "cmd_args": ["sh", "-c", f"{cd_prefix}{preload} npx next {script_name} -H 0.0.0.0 -p 5000"],
                "use_py_wrapper": False,
                "use_node_wrapper": True,
                "node_pkg_rel_dir": pkg_rel_dir,
                "is_web": True,
            }
        if "react-scripts" in deps:
            return {
                "stack": "React (CRA)",
                "mode": "node",
                "cmd_args": ["sh", "-c", f"{cd_prefix}HOST=0.0.0.0 PORT=5000 BROWSER=none {preload} npm start"],
                "use_py_wrapper": False,
                "use_node_wrapper": True,
                "node_pkg_rel_dir": pkg_rel_dir,
                "is_web": True,
            }
        if "start" in scripts or "dev" in scripts:
            script_name = "start" if "start" in scripts else "dev"
            return {
                "stack": "Node.js / Express",
                "mode": "node",
                "cmd_args": ["sh", "-c", f"{cd_prefix}HOST=0.0.0.0 PORT=5000 {preload} npm run {script_name}"],
                "use_py_wrapper": False,
                "use_node_wrapper": True,
                "node_pkg_rel_dir": pkg_rel_dir,
                "is_web": True,
            }
        for js_entry in ("server.js", "index.js", "app.js", "main.js", "src/index.js", "src/server.js"):
            target_js = node_manifest.parent / js_entry
            if target_js.exists():
                rel_js = f"{pkg_rel_dir}/{js_entry}".lstrip("/")
                return {
                    "stack": "Node.js",
                    "mode": "node",
                    "cmd_args": ["node", "--require", "/workspace/_rd_node_wrapper.cjs", rel_js],
                    "use_py_wrapper": False,
                    "use_node_wrapper": True,
                    "node_pkg_rel_dir": pkg_rel_dir,
                    "is_web": True,
                }

    if not found_py:
        all_py = sorted(
            p.name for p in repo_path.glob("*.py")
            if not p.name.startswith(("test_", "_rd_", "conftest"))
        )
        non_setup = [name for name in all_py if not name.startswith(("setup", "make_"))]
        found_py = non_setup[0] if non_setup else (all_py[0] if all_py else None)

    if found_py:
        src = (repo_path / found_py).read_text(encoding="utf-8", errors="ignore")
        if "streamlit" in src:
            return {
                "stack": "Streamlit",
                "mode": "py",
                "cmd_args": ["python", "-m", "streamlit", "run", found_py, "--server.address=0.0.0.0", "--server.port=5000", "--server.headless=true"],
                "use_py_wrapper": False,
                "use_node_wrapper": False,
                "node_pkg_rel_dir": "",
                "is_web": True,
            }
        stack_name = "Python"
        if "FastAPI" in src or "fastapi" in src:
            stack_name = "FastAPI"
        elif "Flask" in src or "flask" in src:
            stack_name = "Flask"
        elif found_py.endswith("manage.py") or "django" in src:
            stack_name = "Django"

        is_web_spa = False
        if node_manifest is not None:
            pkg_p = node_manifest.parent
            try:
                pkg_json = json.loads(node_manifest.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pkg_json = {}
            deps_all = {}
            deps_all.update(pkg_json.get("dependencies") or {})
            deps_all.update(pkg_json.get("devDependencies") or {})
            is_mobile = "expo" in deps_all or "react-native" in deps_all
            is_web_spa = not is_mobile and any(
                (pkg_p / f).exists() for f in ("index.html", "vite.config.js", "vite.config.ts", "public/index.html")
            )

        if has_compiled_spa or (is_py_web_server and is_web_spa):
            stack_name += " / Full-Stack"

        return {
            "stack": stack_name,
            "mode": "py",
            "cmd_args": ["python", "_rd_web_wrapper.py", found_py],
            "use_py_wrapper": True,
            "use_node_wrapper": False,
            "node_pkg_rel_dir": "",
            "needs_frontend_build": bool(is_py_web_server and is_web_spa and not has_compiled_spa),
            "node_manifest_path": str(node_manifest) if (node_manifest is not None and is_web_spa) else "",
            "is_web": True,
        }

    for js_entry in ("server.js", "index.js", "app.js", "main.js"):
        if (repo_path / js_entry).exists():
            return {
                "stack": "Node.js",
                "mode": "node",
                "cmd_args": ["node", "--require", "/workspace/_rd_node_wrapper.cjs", js_entry],
                "use_py_wrapper": False,
                "use_node_wrapper": True,
                "node_pkg_rel_dir": "",
                "is_web": True,
            }

    for html_cand in ("index.html", "frontend/index.html", "public/index.html", "dist/index.html", "test_site/index.html"):
        if (repo_path / html_cand).exists():
            raw_h = (repo_path / html_cand).read_text(encoding="utf-8", errors="ignore")
            if any(t in raw_h for t in ("/src/main.", "/src/index.", "./src/main.", "./src/index.")):
                continue
            html_dir = str(Path(html_cand).parent).replace("\\", "/")
            dir_arg = "." if html_dir == "." else html_dir
            return {
                "stack": "Static HTML/JS",
                "mode": "py",
                "cmd_args": ["python", "_rd_web_wrapper.py", "_rd_static_entry.py"],
                "use_py_wrapper": True,
                "use_node_wrapper": False,
                "static_dir": dir_arg,
                "node_pkg_rel_dir": "",
                "is_web": True,
            }

    for html_file in repo_path.rglob("*.html"):
        if not any(skip in html_file.parts for skip in (".git", "node_modules", ".venv", "__pycache__")):
            raw_h = html_file.read_text(encoding="utf-8", errors="ignore")
            if any(t in raw_h for t in ("/src/main.", "/src/index.", "./src/main.", "./src/index.")):
                continue
            rel_dir = str(html_file.parent.relative_to(repo_path)).replace("\\", "/")
            dir_arg = "." if rel_dir == "." else rel_dir
            return {
                "stack": "HTML/Web Site",
                "mode": "py",
                "cmd_args": ["python", "_rd_web_wrapper.py", "_rd_static_entry.py"],
                "use_py_wrapper": True,
                "use_node_wrapper": False,
                "static_dir": dir_arg,
                "node_pkg_rel_dir": "",
                "is_web": True,
            }

    return {
        "stack": "Generic Workspace",
        "mode": "py",
        "cmd_args": ["python", "-c", "import os; print('Workspace files:', sorted(os.listdir('.')))"],
        "use_py_wrapper": False,
        "use_node_wrapper": False,
        "node_pkg_rel_dir": "",
        "is_web": False,
    }


async def handle_terminal_websocket(
    ws: WebSocket,
    pid: str,
    repo_path: Path,
    emit_event: Optional[Callable[[str, str, dict], Awaitable[None]]] = None,
) -> None:
    await ws.accept()

    async def send_line(stream: str, data: str) -> None:
        await ws.send_json({
            "stream": stream,
            "data": data,
            "ts": int(time.time() * 1000),
        })
        if emit_event and "[ACTIVE_NODE]" in data:
            for m in re.finditer(r"\[ACTIVE_NODE\]\s*([^\r\n]+)", data):
                node_p = m.group(1).strip()
                if node_p:
                    try:
                        await emit_event("node_pulse", pid, {"node_id": node_p})
                    except Exception:
                        pass

    rt_info = await asyncio.to_thread(detect_project_runtime, repo_path)
    await send_line(
        "system",
        f"Connected to Release Domino Sandbox Terminal for '{pid}' | Auto-Detected Stack: [{rt_info['stack']}]\r\n",
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"cmd": raw.strip()}

            if "stdin" in msg and msg.get("stdin") is not None:
                stdin_txt = str(msg.get("stdin"))
                await send_line("system", f"> {stdin_txt}\r\n")
                sent = await asyncio.to_thread(send_stdin_to_process, pid, stdin_txt)
                if not sent:
                    await send_line("stderr", "[Interactive Stdin] No active running process waiting for input.\r\n")
                continue

            cmd_str = str(msg.get("cmd") or "").strip()
            strict_docker = bool(msg.get("strict_docker", False))
            force_local = bool(msg.get("force_local", False))
            keep_alive_sec = int(msg.get("keep_alive_sec", 0) or 0)
            allow_network = bool(msg.get("allow_network", False))
            if not cmd_str:
                continue

            if cmd_str in ("stop", "kill"):
                await send_line("system", f"$ {cmd_str}\r\n")
                stopped = await asyncio.to_thread(stop_project_container_sync, pid)
                await send_line("system", f"[Docker Container Stopped] pid={pid} stopped={stopped}\r\n")
                continue

            # If a program is actively running and the user types interactive input (not a control command), pipe to stdin!
            if cmd_str not in ("run", "test", "install") and is_process_running(pid):
                first_tok = cmd_str.split()[0] if cmd_str.split() else ""
                if first_tok not in ALLOWED_BINARIES:
                    await send_line("system", f"> {cmd_str}\r\n")
                    await asyncio.to_thread(send_stdin_to_process, pid, cmd_str)
                    continue

            await send_line("system", f"$ {cmd_str}\r\n")

            if cmd_str == "install":
                rt = await asyncio.to_thread(detect_project_runtime, repo_path)
                code, _, _ = await install_project_dependencies(pid, repo_path, mode=rt["mode"], force=True, on_line=send_line)
                await send_line("system", f"[Phase 1 Install exited with code {code}]\r\n")
                continue

            if cmd_str == "test":
                res = await run_tests(
                    pid=pid,
                    repo_path=repo_path,
                    emit_event=emit_event,
                    on_terminal_line=send_line,
                    strict_docker=strict_docker,
                    keep_alive_sec=keep_alive_sec,
                )
                summary = (
                    f"[Test Run {res.run_id}] passed={res.passed} failed={res.failed} "
                    f"errors={res.errors} ({res.duration_s}s) | "
                    f"Ran {res.selected_tests} of {res.total_tests} test files\r\n"
                )
                await send_line("system", summary)
                continue

            extra_files: Dict[str, str] = {}
            host_port: Optional[int] = None
            node_pkg_rel_dir = ""
            run_timeout = 120

            if cmd_str == "run":
                await asyncio.to_thread(stop_project_container_sync, pid)

                # 1. High-Confidence RunPlan execution (Zero-Docker / topo_order / port allocation / multi-service)
                try:
                    from app.planner.facts import gather_repo_facts
                    from app.planner.adapters import extract_candidates_from_repo
                    from app.planner.engine import resolve_and_run
                    from app.planner.executor import create_plan_executor

                    facts = await asyncio.to_thread(gather_repo_facts, repo_path)
                    candidates = await asyncio.to_thread(extract_candidates_from_repo, repo_path)
                    if candidates and any(c.score >= 0.8 for c in candidates):
                        roles_desc = ", ".join(f"{c.role} ({c.name})" for c in candidates)
                        await send_line("system", f"[RunPlan Engine] Detected architecture: {roles_desc}\r\n")
                        executor = create_plan_executor(repo_path, pid, on_line=send_line)
                        plan, exec_res = await resolve_and_run(
                            facts=facts,
                            candidates=candidates,
                            repo_path=str(repo_path),
                            executor=executor,
                        )
                        if exec_res.ok:
                            continue
                        else:
                            await send_line(
                                "stderr",
                                f"[RunPlan Engine] Service '{exec_res.failed_service}' failed. Falling back to default runner...\r\n",
                            )
                except Exception as ex:
                    logger.debug("RunPlan engine fallback: %s", ex)

                rt = await asyncio.to_thread(detect_project_runtime, repo_path)
                cmd_args = rt["cmd_args"]
                mode = rt["mode"]
                node_pkg_rel_dir = rt.get("node_pkg_rel_dir", "")

                # Only enable interactive web portal & port publishing when starting from the browser UI (strict_docker or keep_alive_sec > 0)
                if strict_docker or keep_alive_sec > 0:
                    host_port = await asyncio.to_thread(find_free_host_port, 5050)
                    run_timeout = 3600
                    # Do NOT wrap in sleep 15 when running interactive web portal — the web server itself stays alive!
                    keep_alive_sec = 0

                if rt.get("use_py_wrapper"):
                    extra_files["_rd_web_wrapper.py"] = WEB_RUN_WRAPPER
                    if rt.get("static_dir"):
                        sdir = rt["static_dir"]
                        extra_files["_rd_static_entry.py"] = (
                            f"import http.server, functools\n"
                            f"handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory={sdir!r})\n"
                            f"srv = http.server.ThreadingHTTPServer(('0.0.0.0', 5000), handler)\n"
                            f"srv.serve_forever()\n"
                        )
                if rt.get("use_node_wrapper"):
                    extra_files["_rd_node_wrapper.cjs"] = NODE_NET_WRAPPER

                await send_line("system", f"[Stack Detector] Detected {rt['stack']} project (runner={mode})\r\n")

                # If this is a Full-Stack project cloned from GitHub without a compiled dist/ folder,
                # build dist/ inside rd-runner-node first so the Python backend can serve both the SPA and API!
                if rt.get("needs_frontend_build") and rt.get("node_manifest_path"):
                    nm_path = Path(rt["node_manifest_path"])
                    built_ok = await build_frontend_dist(pid, repo_path, nm_path, on_line=send_line)
                    if not built_ok:
                        if rt.get("mode") == "py":
                            await send_line("system", "[Notice] Serving Python API backend directly.\r\n")
                        else:
                            rel_d = str(nm_path.parent.relative_to(repo_path)).replace("\\", "/")
                            node_pkg_rel_dir = "" if rel_d == "." else rel_d
                            cd_p = f"cd /workspace/{node_pkg_rel_dir} && " if node_pkg_rel_dir else ""
                            pre = 'NODE_OPTIONS="--require /workspace/_rd_node_wrapper.cjs"'
                            mode = "node"
                            cmd_args = ["sh", "-c", f"{cd_p}if [ -x ./node_modules/.bin/vite ]; then {pre} ./node_modules/.bin/vite --host 0.0.0.0 --port 5000; else {pre} npm run dev -- --host 0.0.0.0 --port 5000; fi"]
                            extra_files["_rd_node_wrapper.cjs"] = NODE_NET_WRAPPER

                # Auto-install dependencies (Phase 1) for both Python and Node
                if mode == "py" and (_find_manifest(repo_path, "py") is not None or infer_python_requirements(repo_path)):
                    await install_project_dependencies(pid, repo_path, mode="py", force=False, on_line=send_line)
                elif mode == "node" and _find_manifest(repo_path, "node") is not None:
                    await install_project_dependencies(pid, repo_path, mode="node", force=False, on_line=send_line)
            else:
                parts = shlex.split(cmd_str)
                if not parts or parts[0] not in ALLOWED_BINARIES:
                    await send_line(
                        "stderr",
                        f"Blocked command '{cmd_str}': allowed sandbox commands are {sorted(ALLOWED_BINARIES)}\r\n",
                    )
                    continue
                if parts[0] == "pytest":
                    cmd_args = ["python", "-m"] + parts
                else:
                    cmd_args = parts
                mode = "node" if cmd_args[0] in ("jest", "npm", "npx", "node") else "py"

                is_server_cmd = any(
                    x in cmd_str.lower()
                    for x in ("main.py", "app.py", "server.py", "manage.py", "uvicorn", "flask", "streamlit", "http.server", "npm run dev", "npm start", "node")
                )
                if is_server_cmd and (strict_docker or keep_alive_sec > 0):
                    await asyncio.to_thread(stop_project_container_sync, pid)
                    host_port = await asyncio.to_thread(find_free_host_port, 5050)
                    run_timeout = 3600
                    keep_alive_sec = 0
                    extra_files["_rd_web_wrapper.py"] = WEB_RUN_WRAPPER
                    extra_files["_rd_node_wrapper.cjs"] = NODE_NET_WRAPPER

            async def _run_and_finalize():
                try:
                    ec, _, _, s_ws = await run_command(
                        pid=pid,
                        repo_path=repo_path,
                        cmd_args=cmd_args,
                        mode=mode,
                        on_line=send_line,
                        timeout_sec=run_timeout,
                        extra_files=extra_files if extra_files else None,
                        strict_docker=strict_docker,
                        keep_alive_sec=keep_alive_sec,
                        allow_network=allow_network,
                        host_port=host_port,
                        container_port=5000,
                        node_pkg_rel_dir=node_pkg_rel_dir,
                        force_local=force_local,
                    )
                    cleanup_sandbox(s_ws)
                    await send_line("system", f"[Process exited with code {ec}]\r\n")
                except Exception as exc:
                    await send_line("stderr", f"[Process Error] {exc}\r\n")

            if host_port is not None or force_local or msg.get("interactive"):
                asyncio.create_task(_run_and_finalize())
            else:
                await _run_and_finalize()
    except WebSocketDisconnect:
        logger.info("Terminal WS disconnected for project %s", pid)
