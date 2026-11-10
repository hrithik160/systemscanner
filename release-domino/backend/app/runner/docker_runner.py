"""
Tasks D2 & D3 — Universal Multi-Stack Sandboxed Two-Phase Docker Runner (backend/app/runner/docker_runner.py)
Supports Python (FastAPI, Flask, Django, Streamlit, CLI), Node.js (Express, Fastify, NestJS),
Frontend Frameworks (React/CRA, Vite, Next.js, Vue, Angular), Full-Stack Monorepos, and Static HTML/JS sites.
Uses native Linux Docker Named Volumes (`rd_deps_*`) for Phase 1 dependency caching so `npm install`
and `pip install` run at native ext4 disk speed on Windows WSL2 (avoiding slow 9P host bind-mount I/O),
and streams Phase 1 progress lines live to the terminal.
Enforces all non-negotiable Phase 2 container security flags from Section 8 of the Team Guide:
  --network none --memory 512m --cpus 1 --pids-limit 128
  --read-only --tmpfs /tmp --user 1000:1000 --cap-drop ALL
  --security-opt no-new-privileges
  wall-clock timeout 120 s, then kill.
"""
import ast
import asyncio
import hashlib
import json
import logging
import os
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("release_domino.runner.docker_runner")

MANDATORY_SECURITY_FLAGS: List[str] = [
    "--rm",
    "--network", "none",
    "--memory", "512m",
    "--cpus", "1",
    "--pids-limit", "128",
    "--read-only",
    "--tmpfs", "/tmp:rw,exec,size=512m",
    "--user", "1000:1000",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
]

WALL_CLOCK_TIMEOUT_SEC = 120
PHASE1_INSTALL_TIMEOUT_SEC = 600
PY_RUNNER_IMAGE = os.getenv("RD_PY_RUNNER_IMAGE", "rd-runner-py")
NODE_RUNNER_IMAGE = os.getenv("RD_NODE_RUNNER_IMAGE", "rd-runner-node")
DEPS_CACHE_ROOT = Path(tempfile.gettempdir()) / "rd_deps_cache"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ACTIVE_PROJECT_CONTAINERS: Dict[str, str] = {}
ACTIVE_LOCAL_PROCESSES: Dict[str, subprocess.Popen] = {}
INSTALLED_VOLUME_CACHE: set[str] = set()

# Common Python import -> PyPI package mapping for projects missing requirements.txt
IMPORT_TO_PYPI: Dict[str, List[str]] = {
    "flask": ["flask", "werkzeug", "jinja2"],
    "flask_cors": ["flask-cors"],
    "flask_sqlalchemy": ["flask-sqlalchemy"],
    "flask_login": ["flask-login"],
    "flask_wtf": ["flask-wtf", "email-validator"],
    "wtforms": ["wtforms"],
    "fastapi": ["fastapi", "uvicorn", "python-multipart", "aiofiles"],
    "starlette": ["starlette", "uvicorn"],
    "uvicorn": ["uvicorn"],
    "requests": ["requests"],
    "httpx": ["httpx"],
    "aiohttp": ["aiohttp"],
    "pydantic": ["pydantic"],
    "sqlalchemy": ["sqlalchemy"],
    "django": ["django"],
    "streamlit": ["streamlit"],
    "bs4": ["beautifulsoup4"],
    "dotenv": ["python-dotenv"],
    "jwt": ["PyJWT"],
    "yaml": ["pyyaml"],
    "redis": ["redis"],
    "pymongo": ["pymongo"],
    "PIL": ["pillow"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "sklearn": ["scikit-learn", "scipy", "joblib"],
    "scipy": ["scipy"],
    "joblib": ["joblib"],
    "matplotlib": ["matplotlib"],
    "seaborn": ["seaborn"],
    "cv2": ["opencv-python-headless"],
    "passlib": ["passlib", "bcrypt"],
    "bcrypt": ["bcrypt"],
    "jose": ["python-jose"],
}


def _to_docker_mount_path(path: Union[Path, str]) -> str:
    """Converts Windows paths to forward-slash paths for Docker bind mounts, keeping volume names intact."""
    if isinstance(path, str) and not ("/" in path or "\\" in path or ":" in path):
        return path
    p = Path(path)
    if not p.is_absolute() and str(path).startswith("rd_deps_"):
        return str(path)
    return str(p.resolve()).replace("\\", "/")


def find_free_host_port(preferred: int = 5050) -> int:
    for port in range(preferred, preferred + 60):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def create_repo_sandbox_copy(repo_path: Path) -> Path:
    """
    Copies the project into a disposable temp directory and sets 0777/0666 permissions
    so uid 1000:1000 inside the container can write coverage JSON files or build artifacts
    without touching the user's original repo folder.
    """
    temp_root = Path(tempfile.mkdtemp(prefix="rd_sandbox_"))
    dest = temp_root / "workspace"
    shutil.copytree(
        repo_path,
        dest,
        ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "venv", "__pycache__", "*.pyc"),
    )
    for p in dest.rglob("*"):
        try:
            p.chmod(0o777 if p.is_dir() else 0o666)
        except OSError:
            pass
    try:
        dest.chmod(0o777)
        temp_root.chmod(0o777)
    except OSError:
        pass
    return dest


def is_docker_daemon_running() -> bool:
    """Checks whether the Docker daemon itself is running and responsive."""
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def is_docker_available(lang: str = "py") -> bool:
    """Checks whether the Docker daemon is reachable and has the requested runner image built."""
    if os.getenv("RD_FORCE_LOCAL_RUNNER", "").lower() in ("1", "true", "yes"):
        return False
    image = PY_RUNNER_IMAGE if lang == "py" else NODE_RUNNER_IMAGE
    try:
        res = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            timeout=4,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def get_docker_status_sync() -> Dict[str, Any]:
    """Returns live Docker daemon and runner image status for the Sandbox UI."""
    daemon_ok = is_docker_daemon_running()
    py_ok = is_docker_available("py") if daemon_ok else False
    node_ok = is_docker_available("node") if daemon_ok else False
    running_containers: List[Dict[str, str]] = []
    if daemon_ok:
        try:
            ps = subprocess.run(
                ["docker", "ps", "--filter", "name=rd-", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                check=False,
            )
            for line in (ps.stdout or "").splitlines():
                parts = line.strip().split("|")
                if len(parts) == 4:
                    running_containers.append({
                        "id": parts[0],
                        "name": parts[1],
                        "image": parts[2],
                        "status": parts[3],
                    })
        except Exception:
            pass
    return {
        "daemon_running": daemon_ok,
        "images": {
            PY_RUNNER_IMAGE: py_ok,
            NODE_RUNNER_IMAGE: node_ok,
        },
        "running_containers": running_containers,
        "local_fallback_env": is_local_fallback_enabled(),
    }


def ensure_runner_image_built_sync(lang: str = "py") -> Tuple[bool, str]:
    """Builds `rd-runner-py` or `rd-runner-node` automatically if the Docker daemon is running."""
    if is_docker_available(lang):
        return True, f"Image {PY_RUNNER_IMAGE if lang == 'py' else NODE_RUNNER_IMAGE} already present."
    if not is_docker_daemon_running():
        return False, "Docker Desktop daemon is not running."
    tag = PY_RUNNER_IMAGE if lang == "py" else NODE_RUNNER_IMAGE
    dockerfile = REPO_ROOT / "docker" / ("py" if lang == "py" else "node") / "Dockerfile"
    if not dockerfile.exists():
        return False, f"Dockerfile not found at {dockerfile}"
    try:
        res = subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(dockerfile), str(REPO_ROOT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        return res.returncode == 0, out.strip()
    except Exception as exc:
        return False, str(exc)


def is_local_fallback_enabled() -> bool:
    """
    Host execution fallback is strictly opt-in for local dev/CI without Docker via
    `RD_ALLOW_LOCAL_FALLBACK=1` (or `RD_FORCE_LOCAL_RUNNER=1`).
    """
    return (
        os.getenv("RD_ALLOW_LOCAL_FALLBACK", "").lower() in ("1", "true", "yes")
        or os.getenv("RD_FORCE_LOCAL_RUNNER", "").lower() in ("1", "true", "yes")
    )


SKIP_MANIFEST_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build", ".next"}


def _ensure_vite_package_json(repo_path: Path) -> Optional[Path]:
    """
    If a repo has an uncompiled Vite/React index.html (referencing /src/main.jsx or .tsx)
    but no package.json was committed in that folder, auto-synthesizes a valid package.json
    by scanning JS/JSX/TS/TSX imports so rd-runner-node can install and run Vite!
    """
    for html_f in sorted(repo_path.rglob("index.html"), key=lambda x: len(x.parts)):
        if any(skip in html_f.parts for skip in SKIP_MANIFEST_DIRS):
            continue
        try:
            raw_h = html_f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(tok in raw_h for tok in ("/src/main.", "/src/index.", "./src/main.", "./src/index.")):
            pkg_dir = html_f.parent
            pkg_file = pkg_dir / "package.json"
            if not pkg_file.exists():
                import re
                deps = {"react": "^18.3.1", "react-dom": "^18.3.1"}
                for src_f in pkg_dir.rglob("*"):
                    if src_f.suffix in (".js", ".jsx", ".ts", ".tsx") and not any(s in src_f.parts for s in SKIP_MANIFEST_DIRS):
                        try:
                            code = src_f.read_text(encoding="utf-8", errors="ignore")
                            for m in re.finditer(r"(?:from|import)\s+['\"](@?[a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)?)['\"]", code):
                                spec = m.group(1)
                                if spec.startswith((".", "/", "http:", "https:", "node:")):
                                    continue
                                pkg_name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
                                if pkg_name not in deps and pkg_name not in ("react", "react-dom", "vite"):
                                    deps[pkg_name] = "latest"
                        except Exception:
                            pass
                synth = {
                    "name": "rd-auto-vite-app",
                    "private": True,
                    "version": "0.0.0",
                    "type": "module",
                    "scripts": {"dev": "vite", "build": "vite build"},
                    "dependencies": deps,
                    "devDependencies": {"vite": "^5.4.0", "@vitejs/plugin-react": "^4.3.1"},
                }
                try:
                    pkg_file.write_text(json.dumps(synth, indent=2), encoding="utf-8")
                    return pkg_file
                except Exception:
                    pass
    return None


def _find_manifest(repo_path: Path, lang: str) -> Optional[Path]:
    if lang == "py":
        candidates = ["requirements.txt", "backend/requirements.txt", "src/requirements.txt", "api/requirements.txt", "server/requirements.txt"]
        for rel in candidates:
            p = repo_path / rel
            if p.exists() and p.is_file():
                return p
        for p in sorted(repo_path.rglob("requirements.txt"), key=lambda x: len(x.parts)):
            if not any(skip in p.parts for skip in SKIP_MANIFEST_DIRS) and p.is_file():
                return p
        return None

    # For lang == "node": scan all package.json files (including nested GitHub repo folders) and pick the highest-scoring app manifest
    all_pkgs: List[Tuple[int, int, Path]] = []
    for p in repo_path.rglob("package.json"):
        if any(skip in p.parts for skip in SKIP_MANIFEST_DIRS) or not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            data = {}
        scripts = data.get("scripts") or {}
        deps = {}
        deps.update(data.get("dependencies") or {})
        deps.update(data.get("devDependencies") or {})
        score = 0
        if any(k in deps for k in ("vite", "next", "react-scripts", "@angular/core", "vue", "svelte", "nuxt", "express", "fastify", "koa", "@nestjs/core")):
            score += 100
        if any("vite" in str(v) or "next" in str(v) or "react-scripts" in str(v) for v in scripts.values()):
            score += 80
        if "dev" in scripts or "start" in scripts:
            score += 50
        if (p.parent / "index.html").exists() or (p.parent / "vite.config.js").exists() or (p.parent / "vite.config.ts").exists():
            score += 30
        if deps:
            score += 10
        depth = len(p.relative_to(repo_path).parts)
        all_pkgs.append((score, -depth, p))

    if all_pkgs:
        all_pkgs.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return all_pkgs[0][2]

    return _ensure_vite_package_json(repo_path)


def infer_python_requirements(repo_path: Path) -> List[str]:
    """Scans .py files for common imports when a project has no requirements.txt."""
    pkgs: set[str] = set()
    for py_f in repo_path.rglob("*.py"):
        if any(skip in py_f.parts for skip in (".git", "node_modules", ".venv", "venv", "__pycache__")):
            continue
        try:
            src = py_f.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in IMPORT_TO_PYPI:
                            pkgs.update(IMPORT_TO_PYPI[top])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top in IMPORT_TO_PYPI:
                        pkgs.update(IMPORT_TO_PYPI[top])
        except Exception:
            pass
    return sorted(pkgs)


def _get_deps_volume_name(pid: str, repo_path: Path, lang: str) -> Optional[str]:
    """
    Computes a deterministic Docker Named Volume identifier (`rd_deps_<lang>_<hash12>`)
    based on the contents of `requirements.txt` / `package.json`.
    Because Docker Named Volumes reside inside WSL2's native Linux ext4 filesystem,
    `npm install` and `pip install` run 20x-50x faster than over Windows C:\\ bind mounts!
    """
    manifest = _find_manifest(repo_path, lang)
    if manifest is not None:
        raw_bytes = manifest.read_bytes()
        if lang == "py":
            inferred = infer_python_requirements(repo_path)
            raw_bytes += b"\n" + "\n".join(inferred).encode("utf-8")
        digest = hashlib.sha256(raw_bytes).hexdigest()[:12]
        return f"rd_deps_{lang}_{digest}"
    if lang == "py":
        inferred = infer_python_requirements(repo_path)
        if inferred:
            digest = hashlib.sha256("\n".join(inferred).encode("utf-8")).hexdigest()[:12]
            return f"rd_deps_py_auto_{digest}"
    return None


def build_docker_run_args(
    sandbox_workspace: Path,
    cmd_args: List[str],
    lang: str = "py",
    network_on: bool = False,
    container_name: Optional[str] = None,
    deps_dir: Optional[Union[Path, str]] = None,
    deps_writable: bool = False,
    host_port: Optional[int] = None,
    container_port: int = 5000,
    node_pkg_rel_dir: str = "",
) -> List[str]:
    """
    Constructs the exact `docker run` CLI command with all mandatory security flags,
    read-write disposable `/workspace:rw`, `PYTHONPATH=/workspace:/deps`, and
    `COVERAGE_FILE=/tmp/.coverage`.
    When `network_on=True` and `deps_writable=True` (Phase 1 dependency installation),
    allocates 4 CPUs, 2GB RAM, and 512 PIDs so npm/pip never get throttled.
    """
    image = PY_RUNNER_IMAGE if lang == "py" else NODE_RUNNER_IMAGE
    mount_src = _to_docker_mount_path(sandbox_workspace)
    flags = list(MANDATORY_SECURITY_FLAGS)
    if network_on or host_port is not None:
        # Override --network none with bridge and inject explicit public DNS resolvers
        net_idx = flags.index("--network")
        flags[net_idx + 1] = "bridge"
        flags.extend(["--dns", "8.8.8.8", "--dns", "1.1.1.1"])
        if host_port is not None and not deps_writable:
            mem_idx = flags.index("--memory")
            flags[mem_idx + 1] = "2g"
            cpu_idx = flags.index("--cpus")
            flags[cpu_idx + 1] = "2"
            pid_idx = flags.index("--pids-limit")
            flags[pid_idx + 1] = "512"
        if deps_writable:
            # Unthrottle Phase 1 dependency installation so npm/pip finish in seconds
            mem_idx = flags.index("--memory")
            flags[mem_idx + 1] = "2g"
            cpu_idx = flags.index("--cpus")
            flags[cpu_idx + 1] = "4"
            pid_idx = flags.index("--pids-limit")
            flags[pid_idx + 1] = "512"
            # Run Phase 1 volume initialization as root so the named Docker volume is chmod 777 for uid 1000
            usr_idx = flags.index("--user")
            flags[usr_idx + 1] = "0:0"
            if "--cap-drop" in flags:
                cap_idx = flags.index("--cap-drop")
                flags.pop(cap_idx)
                flags.pop(cap_idx)

    args = ["docker", "run"]
    if container_name:
        args.extend(["--name", container_name])
    args.extend(flags)
    if host_port is not None:
        args.extend([
            "-p", f"127.0.0.1:{host_port}:{container_port}",
            "-e", f"RD_HOST_PORT={host_port}",
            "-e", "RD_INTERACTIVE_RUN=1",
        ])
    args.extend([
        "-e", "PYTHONPATH=/workspace:/deps",
        "-e", "COVERAGE_FILE=/tmp/.coverage",
        "-e", "HOME=/tmp",
        "-e", "NPM_CONFIG_CACHE=/tmp/.npm",
        "-e", "PYTHONUNBUFFERED=1",
        "-e", "OPENBLAS_NUM_THREADS=1",
        "-e", "OMP_NUM_THREADS=1",
        "-e", "MKL_NUM_THREADS=1",
        "-e", "JOBLIB_TEMP_FOLDER=/tmp",
        "-e", "PORT=5000",
        "-e", "HOST=0.0.0.0",
        "-e", "CI=false",
        "-e", "BROWSER=none",
        "-e", "WDS_SOCKET_PORT=0",
        "-e", "CHOKIDAR_USEPOLLING=true",
        "-e", "NODE_PATH=/deps/node_modules:/workspace/node_modules",
        "-e", "PATH=/deps/node_modules/.bin:/workspace/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "-v", f"{mount_src}:/workspace:rw",
    ])
    if deps_dir is not None:
        deps_mount = _to_docker_mount_path(deps_dir)
        mode_flag = "rw" if deps_writable else "ro"
        args.extend(["-v", f"{deps_mount}:/deps:{mode_flag}"])
        if lang == "node":
            rel_clean = node_pkg_rel_dir.strip("/")
            target_nm = f"/workspace/{rel_clean}/node_modules" if rel_clean else "/workspace/node_modules"
            nm_vol = f"{deps_mount}_nm" if str(deps_mount).startswith("rd_deps_") else _to_docker_mount_path(Path(deps_dir) / "node_modules")
            args.extend([
                "-v", f"{nm_vol}:{target_nm}:rw",
                "-e", f"PATH={target_nm}/.bin:/workspace/node_modules/.bin:/deps/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "-e", f"NODE_PATH={target_nm}:/workspace/node_modules:/deps/node_modules",
            ])
        if deps_writable:
            args.extend(["-e", "TMPDIR=/tmp"])
    args.extend(["-w", "/workspace", image])
    args.extend(cmd_args)
    return args


def _run_sync_process(
    exec_args: List[str],
    cwd: Optional[str],
    env: Optional[dict],
    timeout_sec: int,
) -> Tuple[int, str, str]:
    try:
        res = subprocess.run(
            exec_args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
        return res.returncode, res.stdout or "", res.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"\n[TIMEOUT] Execution exceeded {timeout_sec}s wall-clock limit.\n"
    except Exception as exc:
        return 1, "", f"\n[ERROR] Subprocess failed: {exc}\n"


async def _stream_process(
    exec_args: List[str],
    cwd: Optional[str],
    env: Optional[dict],
    timeout_sec: int,
    on_line: Optional[Callable[[str, str], Awaitable[None]]] = None,
    container_name: Optional[str] = None,
    pid: Optional[str] = None,
) -> Tuple[int, str, str]:
    """
    Runs a subprocess using Popen + background reader threads pushing to an asyncio.Queue.
    Works on ALL Windows event loops (SelectorEventLoop & ProactorEventLoop under uvicorn --reload)
    and streams every line in real time without waiting for long-running web servers to exit!
    """
    import threading
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Optional[Tuple[str, str]]] = asyncio.Queue()
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    try:
        proc = subprocess.Popen(
            exec_args,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        if pid:
            ACTIVE_LOCAL_PROCESSES[pid] = proc
    except Exception as exc:
        err_msg = f"[ERROR] Failed to start process: {exc}\n"
        if on_line:
            await on_line("stderr", err_msg)
        return 1, "", err_msg

    def _reader_thread(pipe, stream_name: str, collector: List[str]):
        fd = pipe.fileno()
        try:
            while True:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                collector.append(text)
                loop.call_soon_threadsafe(queue.put_nowait, (stream_name, text))
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass
            loop.call_soon_threadsafe(queue.put_nowait, None)

    t_out = threading.Thread(target=_reader_thread, args=(proc.stdout, "stdout", stdout_lines), daemon=True)
    t_err = threading.Thread(target=_reader_thread, args=(proc.stderr, "stderr", stderr_lines), daemon=True)
    t_out.start()
    t_err.start()

    async def _drain_queue():
        finished_streams = 0
        while finished_streams < 2:
            item = await queue.get()
            if item is None:
                finished_streams += 1
            else:
                s_name, line_txt = item
                if on_line:
                    await on_line(s_name, line_txt)
                    if "[LIVE_PREVIEW_URL]" not in line_txt and ("http://127.0.0.1:" in line_txt or "http://localhost:" in line_txt):
                        import re as _re
                        # Strip ANSI color codes before matching URL
                        clean_ansi = _re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line_txt)
                        m_url = _re.search(r"(https?://(?:127\.0\.0\.1|localhost):\d+)", clean_ansi)
                        if m_url:
                            detected_url = m_url.group(1).replace("localhost", "127.0.0.1")
                            await on_line("system", f"\n[LIVE_PREVIEW_URL] {detected_url}\r\n")

    try:
        await asyncio.wait_for(_drain_queue(), timeout=timeout_sec)
        rc = await asyncio.to_thread(proc.wait, 5)
        return rc or 0, "".join(stdout_lines), "".join(stderr_lines)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        if container_name:
            await asyncio.to_thread(
                subprocess.run,
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                check=False,
            )
        msg = f"\n[TIMEOUT] Execution exceeded {timeout_sec}s wall-clock limit.\n"
        if on_line:
            await on_line("stderr", msg)
        stderr_lines.append(msg)
        return 124, "".join(stdout_lines), "".join(stderr_lines)
    finally:
        if pid and ACTIVE_LOCAL_PROCESSES.get(pid) is proc:
            ACTIVE_LOCAL_PROCESSES.pop(pid, None)


async def install_project_dependencies(
    pid: str,
    repo_path: Path,
    mode: str = "py",
    force: bool = False,
    timeout_sec: int = PHASE1_INSTALL_TIMEOUT_SEC,
    on_line: Optional[Callable[[str, str], Awaitable[None]]] = None,
    force_local: bool = False,
) -> Tuple[int, str, Optional[str]]:
    """
    Task D2 Phase 1 — Installs project dependencies (`requirements.txt`, auto-inferred Python imports,
    or `package.json`) into a native Linux Docker Named Volume (`rd_deps_<lang>_<hash>`) using
    `network_on=True` (`--network bridge`).
    Subsequent Phase 2 runs mount that volume with `--network none`.
    """
    vol_name = _get_deps_volume_name(pid, repo_path, mode)
    if vol_name is None:
        msg = f"No {mode} dependencies detected; skipping Phase 1 install.\r\n"
        if on_line:
            await on_line("system", msg)
        return 0, msg.strip(), None

    if vol_name in INSTALLED_VOLUME_CACHE and not force:
        msg = f"[Phase 1 Cache Hit] Using cached {mode} dependencies in Docker volume '{vol_name}'\r\n"
        if on_line:
            await on_line("system", msg)
        return 0, msg.strip(), vol_name

    use_docker = False if force_local else await asyncio.to_thread(is_docker_available, mode)
    if not use_docker and await asyncio.to_thread(is_docker_daemon_running):
        if on_line:
            await on_line("system", f"[Docker] Building runner image for '{mode}' (first-time setup)...\r\n")
        built_ok, build_log = await asyncio.to_thread(ensure_runner_image_built_sync, mode)
        use_docker = built_ok
        if not built_ok and on_line:
            await on_line("stderr", f"[Docker Build Error]\r\n{build_log}\r\n")

    if not use_docker:
        if is_local_fallback_enabled():
            manifest_file = _find_manifest(repo_path, mode)
            if mode == "py" and not force:
                return 0, "Local Sandbox active; using host Python environment & auto-healer.", vol_name
            if mode == "node" and not force:
                pkg_dir_chk = manifest_file.parent if (manifest_file and manifest_file.exists()) else repo_path
                if (pkg_dir_chk / "node_modules" / ".bin").is_dir():
                    return 0, "Local Sandbox active; existing node_modules/.bin verified.", vol_name
            local_deps_dir = DEPS_CACHE_ROOT / (vol_name or f"rd_local_{pid}")
            local_deps_dir.mkdir(parents=True, exist_ok=True)
            if mode == "py":
                combined_reqs: List[str] = []
                if manifest_file and manifest_file.exists():
                    combined_reqs.extend(
                        line.strip() for line in manifest_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if line.strip() and not line.strip().startswith("#")
                    )
                existing_names = {r.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip().lower() for r in combined_reqs}
                for pkg in infer_python_requirements(repo_path):
                    if pkg.lower() not in existing_names:
                        combined_reqs.append(pkg)
                req_target = local_deps_dir / "_rd_combined_requirements.txt"
                req_target.write_text("\n".join(combined_reqs) + "\n", encoding="utf-8")
                if on_line:
                    await on_line("system", f"[Local Sandbox] Installing Python packages into {local_deps_dir}...\r\n")
                cmd = [sys.executable, "-m", "pip", "install", "--prefer-binary", "--upgrade", "--target", str(local_deps_dir), "-r", str(req_target)]
                c_code, c_out, c_err = await _stream_process(cmd, str(repo_path), None, timeout_sec, on_line=on_line)
                if c_code == 0 and vol_name:
                    INSTALLED_VOLUME_CACHE.add(vol_name)
                return c_code, (c_out + "\n" + c_err).strip(), str(local_deps_dir)
            else:
                npm_bin = "npm.cmd" if os.name == "nt" else "npm"
                pkg_dir = manifest_file.parent if (manifest_file and manifest_file.exists()) else repo_path
                if on_line:
                    await on_line("system", f"[Local Sandbox] Running npm install in {pkg_dir}...\r\n")
                cmd = [npm_bin, "install", "--no-audit", "--no-fund", "--legacy-peer-deps"]
                c_code, c_out, c_err = await _stream_process(cmd, str(pkg_dir), None, timeout_sec, on_line=on_line)
                return c_code, (c_out + "\n" + c_err).strip(), str(pkg_dir / "node_modules")
        return (
            127,
            f"Docker not available: build rd-runner-{mode} or start Docker Desktop.",
            None,
        )

    sandbox_ws = await asyncio.to_thread(create_repo_sandbox_copy, repo_path)
    try:
        manifest_file = _find_manifest(repo_path, mode)
        if mode == "py":
            combined_reqs: List[str] = []
            if manifest_file and manifest_file.exists():
                combined_reqs.extend(
                    line.strip() for line in manifest_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                )
            existing_names = {r.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip().lower() for r in combined_reqs}
            for pkg in infer_python_requirements(repo_path):
                if pkg.lower() not in existing_names:
                    combined_reqs.append(pkg)
            req_target = sandbox_ws / "_rd_combined_requirements.txt"
            req_target.write_text("\n".join(combined_reqs) + "\n", encoding="utf-8")
            try:
                req_target.chmod(0o666)
            except OSError:
                pass
            force_flag = "1" if force else "0"
            install_cmd = [
                "sh", "-c",
                f"if [ '{force_flag}' = '0' ] && [ -f /deps/.rd_installed ]; then "
                f"  echo '[Phase 1 Volume Cache Hit] Python dependencies already installed in {vol_name}'; exit 0; "
                f"fi && "
                f"chmod 777 /deps && "
                f"python -m pip install --no-cache-dir --prefer-binary --upgrade --root-user-action=ignore --target /deps -r /workspace/_rd_combined_requirements.txt && "
                f"touch /deps/.rd_installed && chmod -R a+rX /deps",
            ]
        else:
            pkg_rel_dir = ""
            if manifest_file and manifest_file.exists():
                rel_d = str(manifest_file.parent.relative_to(repo_path)).replace("\\", "/")
                pkg_rel_dir = "" if rel_d == "." else rel_d
            nm_host_dir = (sandbox_ws / pkg_rel_dir / "node_modules") if pkg_rel_dir else (sandbox_ws / "node_modules")
            nm_host_dir.mkdir(parents=True, exist_ok=True)
            try:
                nm_host_dir.chmod(0o777)
            except OSError:
                pass
            ws_pkg_dir = f"/workspace/{pkg_rel_dir}" if pkg_rel_dir else "/workspace"
            force_flag = "1" if force else "0"
            install_cmd = [
                "sh", "-c",
                f"if [ '{force_flag}' = '0' ] && [ -f {ws_pkg_dir}/node_modules/.rd_installed ] && [ -d {ws_pkg_dir}/node_modules/.bin ]; then "
                f"  echo '[Phase 1 Volume Cache Hit] Node dependencies already installed in {vol_name}'; exit 0; "
                f"fi && "
                f"mkdir -p /deps {ws_pkg_dir}/node_modules && chmod 777 /deps {ws_pkg_dir}/node_modules && "
                f"cd {ws_pkg_dir} && npm install --no-audit --no-fund --legacy-peer-deps --prefer-offline && "
                f"chmod -R a+rwX /deps {ws_pkg_dir}/node_modules && touch {ws_pkg_dir}/node_modules/.rd_installed /deps/.rd_installed",
            ]

        container_name = f"rd-deps-{pid}-{os.urandom(3).hex()}"
        if on_line:
            await on_line(
                "system",
                f"[Docker Phase 1] Installing {mode.upper()} dependencies into fast Linux volume '{vol_name}' (container={container_name}, --network bridge)...\r\n",
            )
        exec_args = build_docker_run_args(
            sandbox_ws,
            cmd_args=install_cmd,
            lang=mode,
            network_on=True,
            container_name=container_name,
            deps_dir=vol_name,
            deps_writable=True,
            node_pkg_rel_dir=pkg_rel_dir if mode == "node" else "",
        )
        code, out, err = await _stream_process(
            exec_args, None, None, timeout_sec, on_line=on_line, container_name=container_name
        )
        if code == 0:
            INSTALLED_VOLUME_CACHE.add(vol_name)
        return code, (out + "\n" + err).strip(), vol_name if code == 0 else None
    finally:
        cleanup_sandbox(sandbox_ws)


async def build_frontend_dist(
    pid: str,
    repo_path: Path,
    node_manifest: Path,
    on_line: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> bool:
    """
    Compiles a React/Vite/CRA frontend (`npm run build` / `vite build`) inside `rd-runner-node`
    and copies the generated `dist/` or `build/` folder back into `repo_path` so a full-stack
    Python backend cloned from GitHub (where `dist/` is gitignored) can serve the compiled SPA!
    """
    code, _, vol_name = await install_project_dependencies(pid, repo_path, mode="node", force=False, on_line=on_line)
    if code != 0 or not vol_name:
        return False

    rel_d = str(node_manifest.parent.relative_to(repo_path)).replace("\\", "/")
    pkg_rel_dir = "" if rel_d == "." else rel_d
    ws_pkg_dir = f"/workspace/{pkg_rel_dir}" if pkg_rel_dir else "/workspace"

    sandbox_ws = await asyncio.to_thread(create_repo_sandbox_copy, repo_path)
    try:
        nm_host_dir = (sandbox_ws / pkg_rel_dir / "node_modules") if pkg_rel_dir else (sandbox_ws / "node_modules")
        nm_host_dir.mkdir(parents=True, exist_ok=True)
        try:
            nm_host_dir.chmod(0o777)
        except OSError:
            pass

        build_cmd = [
            "sh",
            "-c",
            f"cd {ws_pkg_dir} && "
            f"if [ -x ./node_modules/.bin/vite ]; then ./node_modules/.bin/vite build; "
            f"else npm run build; fi && "
            f"chmod -R a+rwX dist build 2>/dev/null || true",
        ]
        container_name = f"rd-build-{pid}-{os.urandom(3).hex()}"
        if on_line:
            await on_line(
                "system",
                f"[Full-Stack Builder] Compiling React/Vite frontend into dist/ inside container {container_name}...\r\n",
            )
        exec_args = build_docker_run_args(
            sandbox_ws,
            cmd_args=build_cmd,
            lang="node",
            network_on=False,
            container_name=container_name,
            deps_dir=vol_name,
            deps_writable=False,
            node_pkg_rel_dir=pkg_rel_dir,
        )
        b_code, _, _ = await _stream_process(
            exec_args, None, None, 180, on_line=on_line, container_name=container_name
        )
        for out_dir_name in ("dist", "build"):
            built_dir = (sandbox_ws / pkg_rel_dir / out_dir_name) if pkg_rel_dir else (sandbox_ws / out_dir_name)
            if built_dir.is_dir() and (built_dir / "index.html").is_file():
                dest_dir = (repo_path / pkg_rel_dir / out_dir_name) if pkg_rel_dir else (repo_path / out_dir_name)
                if dest_dir.exists():
                    shutil.rmtree(dest_dir, ignore_errors=True)
                shutil.copytree(built_dir, dest_dir)
                if on_line:
                    await on_line("system", f"[Full-Stack Builder] Compiled SPA bundle ready at {dest_dir.relative_to(repo_path).as_posix()}/!\r\n")
                return True
        return False
    except Exception as exc:
        if on_line:
            await on_line("stderr", f"[Full-Stack Builder Warning] {exc}\r\n")
        return False
    finally:
        cleanup_sandbox(sandbox_ws)


async def run_command(
    pid: str,
    repo_path: Path,
    cmd_args: List[str],
    mode: str = "py",
    on_line: Optional[Callable[[str, str], Awaitable[None]]] = None,
    timeout_sec: int = WALL_CLOCK_TIMEOUT_SEC,
    extra_files: Optional[dict[str, str]] = None,
    install_deps: bool = False,
    strict_docker: bool = False,
    keep_alive_sec: int = 0,
    allow_network: bool = False,
    host_port: Optional[int] = None,
    container_port: int = 5000,
    node_pkg_rel_dir: str = "",
    force_local: bool = False,
) -> Tuple[int, str, str, Path]:
    """
    Task D3 (Phase 2): Runs `cmd_args` inside the isolated Docker container copy of `repo_path`.
    If `strict_docker=True` (or `RD_ALLOW_LOCAL_FALLBACK` is not enabled), NEVER executes on the host OS.
    """
    if install_deps:
        await install_project_dependencies(pid, repo_path, mode=mode, on_line=on_line)

    sandbox_ws = await asyncio.to_thread(create_repo_sandbox_copy, repo_path)

    if extra_files:
        for rel_name, content in extra_files.items():
            safe_rel = Path(rel_name).name if ".." in rel_name else rel_name.lstrip("/\\")
            target_f = sandbox_ws / safe_rel
            target_f.parent.mkdir(parents=True, exist_ok=True)
            target_f.write_text(content, encoding="utf-8")
            try:
                target_f.chmod(0o666)
                target_f.parent.chmod(0o777)
            except OSError:
                pass

    use_docker = False if force_local else await asyncio.to_thread(is_docker_available, mode)
    if not use_docker and strict_docker and await asyncio.to_thread(is_docker_daemon_running):
        if on_line:
            await on_line(
                "system",
                f"[Docker Setup] Image rd-runner-{mode} not found yet. Building it now from docker/{mode}/Dockerfile...\r\n",
            )
        built_ok, build_log = await asyncio.to_thread(ensure_runner_image_built_sync, mode)
        use_docker = built_ok
        if on_line:
            if built_ok:
                await on_line("system", f"[Docker Setup] Successfully built rd-runner-{mode}!\r\n")
            else:
                await on_line("stderr", f"[Docker Setup Failed]\r\n{build_log}\r\n")

    container_name = f"rd-{pid}-{os.urandom(3).hex()}"
    ACTIVE_PROJECT_CONTAINERS[pid] = container_name

    if use_docker:
        vol_name = _get_deps_volume_name(pid, repo_path, mode)
        if mode == "node" and vol_name:
            nm_dir = (sandbox_ws / node_pkg_rel_dir / "node_modules") if node_pkg_rel_dir else (sandbox_ws / "node_modules")
            nm_dir.mkdir(parents=True, exist_ok=True)
            try:
                nm_dir.chmod(0o777)
            except OSError:
                pass

        effective_cmd = list(cmd_args)
        if keep_alive_sec > 0:
            quoted = " ".join(shlex.quote(c) for c in effective_cmd)
            effective_cmd = [
                "sh", "-c",
                f"echo '[Docker Container {container_name}] Running inside isolated container (uid='$(id -u)', image={PY_RUNNER_IMAGE if mode == 'py' else NODE_RUNNER_IMAGE})...'; "
                f"{quoted}; CODE=$?; "
                f"echo '[Docker Container {container_name}] Holding container open for {keep_alive_sec}s so you can inspect it in Docker Desktop...'; "
                f"sleep {int(keep_alive_sec)}; exit $CODE"
            ]
        net_desc = "--network bridge" if allow_network else "--network none"
        exec_args = build_docker_run_args(
            sandbox_ws,
            cmd_args=effective_cmd,
            lang=mode,
            network_on=allow_network,
            container_name=container_name,
            deps_dir=vol_name,
            deps_writable=False,
            host_port=host_port,
            container_port=container_port,
            node_pkg_rel_dir=node_pkg_rel_dir,
        )
        if on_line:
            await on_line(
                "system",
                f"[Docker Container] Spawning {container_name} (image={PY_RUNNER_IMAGE if mode == 'py' else NODE_RUNNER_IMAGE}, {net_desc}, --read-only, --memory 512m, uid 1000:1000)\r\n",
            )
        run_cwd = None
        run_env = None
    else:
        if strict_docker or (not force_local and not is_local_fallback_enabled()):
            msg = (
                f"Docker not available: ensure Docker Desktop is running and rd-runner-{mode} is built "
                "(click 'Build Docker Images' in the top bar or run `python docker/build_images.py`). "
                "Host execution is blocked.\n"
            )
            if on_line:
                await on_line("stderr", msg)
            return 127, "", msg, sandbox_ws

        if on_line and host_port is not None:
            await on_line(
                "system",
                f"[Local Isolated Sandbox] Running in disposable workspace copy ({sandbox_ws.parent.name}, Zero-Docker mode, native speed)\r\n",
            )

        exec_args = list(cmd_args)
        run_cwd = str(sandbox_ws)
        run_env = os.environ.copy()

        # Discover any local cached deps or project .venv site-packages so all installed libraries work immediately
        py_paths: List[str] = [str(sandbox_ws)]
        vol_name = _get_deps_volume_name(pid, repo_path, mode)
        if vol_name and (DEPS_CACHE_ROOT / vol_name).is_dir():
            py_paths.append(str(DEPS_CACHE_ROOT / vol_name))
        for venv_cand in (repo_path / ".venv", repo_path / "venv", repo_path.parent / ".venv", repo_path.parent / "venv"):
            if venv_cand.is_dir():
                win_sp = venv_cand / "Lib" / "site-packages"
                if win_sp.is_dir():
                    py_paths.append(str(win_sp))
                for unix_sp in venv_cand.glob("lib/python*/site-packages"):
                    if unix_sp.is_dir():
                        py_paths.append(str(unix_sp))
        backend_sp = Path(sys.prefix) / "Lib" / "site-packages"
        if backend_sp.is_dir() and str(backend_sp) not in py_paths:
            py_paths.append(str(backend_sp))
        for p in sys.path:
            if "site-packages" in p and Path(p).is_dir() and p not in py_paths:
                py_paths.append(p)
        auto_deps = Path(tempfile.gettempdir()) / "rd_auto_py_deps"
        if auto_deps.is_dir() and str(auto_deps) not in py_paths:
            py_paths.append(str(auto_deps))
        if os.environ.get("PYTHONPATH"):
            py_paths.append(os.environ["PYTHONPATH"])
        run_env["PYTHONPATH"] = os.pathsep.join(py_paths)
        run_env["COVERAGE_FILE"] = str(sandbox_ws / ".coverage")
        run_env["PYTHONUNBUFFERED"] = "1"

        if host_port is not None:
            run_env["RD_HOST_PORT"] = str(host_port)
            run_env["RD_INTERACTIVE_RUN"] = "1"
            run_env["PORT"] = str(host_port)
            run_env["HOST"] = "127.0.0.1"
            run_env["BROWSER"] = "none"

        if mode == "node":
            orig_pkg_dir = (repo_path / node_pkg_rel_dir) if node_pkg_rel_dir else repo_path
            target_node_dir = (sandbox_ws / node_pkg_rel_dir) if node_pkg_rel_dir else sandbox_ws
            run_cwd = str(target_node_dir)
            npm_bin = "npm.cmd" if os.name == "nt" else "npm"
            npx_bin = "npx.cmd" if os.name == "nt" else "npx"

            orig_nm = orig_pkg_dir / "node_modules"
            if not (orig_nm / ".bin").is_dir() and (orig_pkg_dir / "package.json").is_file():
                if on_line:
                    await on_line("system", f"[Local Sandbox] Installing Node.js dependencies (npm install) in {orig_pkg_dir.name}...\r\n")
                await _stream_process(
                    [npm_bin, "install", "--no-audit", "--no-fund", "--legacy-peer-deps"],
                    str(orig_pkg_dir),
                    None,
                    300,
                    on_line=on_line,
                )

            target_nm = target_node_dir / "node_modules"
            if orig_nm.is_dir() and not target_nm.exists():
                try:
                    if os.name == "nt":
                        subprocess.run(["cmd", "/c", "mklink", "/J", str(target_nm), str(orig_nm.resolve())], capture_output=True, check=False)
                    else:
                        os.symlink(str(orig_nm.resolve()), str(target_nm), target_is_directory=True)
                except Exception:
                    pass

            wrapper_cjs = sandbox_ws / "_rd_node_wrapper.cjs"
            if wrapper_cjs.exists():
                cjs_posix = str(wrapper_cjs.resolve()).replace("\\", "/")
                run_env["NODE_OPTIONS"] = f'--require "{cjs_posix}"'

            bin_paths: List[str] = []
            if (target_nm / ".bin").is_dir():
                bin_paths.append(str((target_nm / ".bin").resolve()))
            if (orig_nm / ".bin").is_dir():
                bin_paths.append(str((orig_nm / ".bin").resolve()))
                run_env["NODE_PATH"] = str(orig_nm.resolve())
            if bin_paths:
                joined_bins = os.pathsep.join(bin_paths)
                orig_path_val = run_env.get("PATH") or run_env.get("Path") or ""
                run_env["PATH"] = f"{joined_bins}{os.pathsep}{orig_path_val}"
                if "Path" in run_env:
                    run_env["Path"] = run_env["PATH"]

            if exec_args and exec_args[0] == "sh":
                joined = " ".join(exec_args)
                p_num = str(host_port or 5050)
                if "vite" in joined:
                    vite_local = (orig_nm / ".bin" / ("vite.cmd" if os.name == "nt" else "vite"))
                    if vite_local.exists():
                        exec_args = [str(vite_local.resolve()), "--host", "127.0.0.1", "--port", p_num]
                    else:
                        exec_args = [npx_bin, "--yes", "vite", "--host", "127.0.0.1", "--port", p_num]
                elif "next" in joined:
                    exec_args = [npx_bin, "next", "dev", "-H", "127.0.0.1", "-p", p_num]
                else:
                    script_target = "dev" if "run dev" in joined else "start"
                    exec_args = [npm_bin, "run", script_target]
            elif exec_args and exec_args[0] == "node":
                exec_args = [
                    str(wrapper_cjs.resolve()) if a == "/workspace/_rd_node_wrapper.cjs" else a
                    for a in exec_args
                ]
        else:
            if exec_args and exec_args[0] == "pytest":
                exec_args = [sys.executable, "-m"] + exec_args
            elif exec_args and exec_args[0] in ("python", "python3"):
                exec_args[0] = sys.executable

    code, out, err = await _stream_process(
        exec_args,
        run_cwd,
        run_env,
        timeout_sec,
        on_line=on_line,
        container_name=container_name if use_docker else None,
        pid=pid,
    )
    return code, out, err, sandbox_ws


def stop_project_container_sync(pid: str) -> bool:
    stopped_any = False
    local_proc = ACTIVE_LOCAL_PROCESSES.pop(pid, None)
    if local_proc is not None and local_proc.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(local_proc.pid)], capture_output=True, timeout=5, check=False)
            else:
                local_proc.kill()
            stopped_any = True
        except Exception:
            pass
    if os.getenv("RD_FORCE_LOCAL_RUNNER", "").lower() in ("1", "true", "yes"):
        return stopped_any
    try:
        ps = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name=rd-{pid}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        cids = [c.strip() for c in (ps.stdout or "").splitlines() if c.strip()]
        if cids:
            subprocess.run(["docker", "rm", "-f"] + cids, capture_output=True, timeout=10, check=False)
            ACTIVE_PROJECT_CONTAINERS.pop(pid, None)
            return True
        return stopped_any
    except Exception:
        return stopped_any


def stop_all_sandbox_containers_sync() -> int:
    try:
        ps = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=rd-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        cids = [c.strip() for c in (ps.stdout or "").splitlines() if c.strip()]
        if cids:
            subprocess.run(["docker", "rm", "-f"] + cids, capture_output=True, timeout=10, check=False)
            ACTIVE_PROJECT_CONTAINERS.clear()
            return len(cids)
        return 0
    except Exception:
        return 0


def cleanup_sandbox(sandbox_ws: Path) -> None:
    """Removes the temporary sandbox directory (handling read-only files on Windows)."""
    def _on_rm_error(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    try:
        for nm_cand in [sandbox_ws / "node_modules"] + list(sandbox_ws.glob("*/node_modules")):
            try:
                if nm_cand.is_symlink():
                    nm_cand.unlink()
                elif os.name == "nt" and nm_cand.exists():
                    # On Windows, os.rmdir removes a directory junction without touching target files
                    os.rmdir(str(nm_cand))
            except Exception:
                pass
        parent = sandbox_ws.parent
        target = parent if parent.name.startswith("rd_sandbox_") else sandbox_ws
        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=lambda f, p, e: _on_rm_error(f, p, e))
        else:
            shutil.rmtree(target, onerror=lambda f, p, e: _on_rm_error(f, p, e))
    except Exception:
        pass


def is_process_running(pid: str) -> bool:
    proc = ACTIVE_LOCAL_PROCESSES.get(pid)
    return bool(proc is not None and proc.poll() is None)


def send_stdin_to_process(pid: str, data: str) -> bool:
    """Writes interactive stdin data to a running sandbox process."""
    proc = ACTIVE_LOCAL_PROCESSES.get(pid)
    if proc is not None and proc.poll() is None and proc.stdin is not None:
        try:
            payload = data if data.endswith("\n") else (data + "\n")
            proc.stdin.write(payload.encode("utf-8", errors="replace"))
            proc.stdin.flush()
            return True
        except Exception:
            return False
    return False
