from __future__ import annotations

import asyncio
import os
import re
import socket
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

import psutil

try:
    from app.planner.facts import gather_repo_facts
    from app.planner.schema import RunPlan, ServiceSpec, topo_order
    from app.planner.engine import ExecResult
    from app.runner.docker_runner import ACTIVE_LOCAL_PROCESSES
except ImportError:
    from facts import gather_repo_facts
    from schema import RunPlan, ServiceSpec, topo_order
    from engine import ExecResult
    ACTIVE_LOCAL_PROCESSES = {}

HTTP_LOG_PATH_RE = re.compile(
    r"""(?:"(?:GET|POST|PUT|DELETE|PATCH|OPTIONS)\s+(/[^"\s?]*)|"""
    r"""(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s?]*)\s+(?:200|201|204|304|400|401|403|404|422|500))"""
)


def _find_free_port(start_port: int = 5050, used: Optional[Set[int]] = None) -> int:
    used = used or set()
    for port in range(start_port, start_port + 200):
        if port in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def _detect_actual_listening_port(root_pid: int, preferred_port: int) -> int:
    """
    Inspects the OS TCP socket table across `root_pid` and all child processes.
    If the service (e.g. Go, Rust, Java, custom Vite config) ignored `{PORT}` and bound to
    a hardcoded port (like 3000 or 8080), returns that actual listening port!
    """
    try:
        parent = psutil.Process(root_pid)
        procs = [parent] + parent.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return preferred_port

    discovered: List[int] = []
    for p in procs:
        try:
            for conn in p.net_connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    port = conn.laddr.port
                    if port == preferred_port:
                        return preferred_port
                    discovered.append(port)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return discovered[0] if discovered else preferred_port


def _normalize_service_cmd(workspace: Path, svc_cwd: Path, cmd: List[str]) -> List[str]:
    """
    1. Resolves `_rd_web_wrapper.py` to its absolute workspace path so nested `cwd` services find it.
    2. Strips duplicate `cwd` prefixes from script arguments (e.g., `backend/app/main.py` -> `app/main.py`).
    """
    norm: List[str] = []
    try:
        rel_cwd = svc_cwd.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        rel_cwd = ""
    if rel_cwd == ".":
        rel_cwd = ""

    for token in cmd:
        if token == "_rd_web_wrapper.py":
            wrapper_abs = (workspace / "_rd_web_wrapper.py").resolve()
            norm.append(str(wrapper_abs))
        elif rel_cwd and token.replace("\\", "/").startswith(f"{rel_cwd}/"):
            stripped = token.replace("\\", "/")[len(rel_cwd) + 1 :]
            norm.append(stripped)
        else:
            norm.append(token)
    return norm


def _substitute_placeholders(
    value: str,
    host: str,
    port: int,
    service_urls: Dict[str, str],
) -> str:
    out = value.replace("{HOST}", host).replace("{PORT}", str(port))
    for svc_name, url in service_urls.items():
        out = out.replace(f"{{services.{svc_name}.url}}", url)
    return out


async def _probe_http(url: str, timeout: float = 1.5) -> bool:
    def _sync_get() -> bool:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ReleaseDomino-Readiness/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= resp.status < 500
        except urllib.error.HTTPError as e:
            return 200 <= e.code < 500
        except Exception:
            return False

    return await asyncio.to_thread(_sync_get)


async def _probe_tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


class PlanExecResult(ExecResult):
    """Subclass of ExecResult supporting both attribute access and tuple unpacking."""
    def __iter__(self):
        return iter((self.ok, self.log, self.failed_service))


def create_plan_executor(
    workspace: Path | str,
    pid: str,
    on_line: Optional[Callable[..., Any]] = None,
    register_process: Optional[Callable[[str, Any], None]] = None,
    host_ip: str = "127.0.0.1",
    base_port: int = 5050,
):
    """
    Creates an async executor closure conforming to `engine.py` that runs a validated `RunPlan`,
    streams logs, emits `[ACTIVE_NODE]` pulses for any stack, adopts OS-level listening ports,
    and verifies readiness before streaming `[LIVE_PREVIEW_URL]`.
    """
    ws_path = Path(workspace).resolve()
    facts = gather_repo_facts(ws_path)
    route_map = facts.route_map

    async def emit_log(line: str, stream: str = "system") -> None:
        if not on_line:
            return
        try:
            if asyncio.iscoroutinefunction(on_line):
                # Check parameter count
                import inspect
                sig = inspect.signature(on_line)
                if len(sig.parameters) >= 2:
                    await on_line(stream, line)
                else:
                    await on_line(line)
            else:
                on_line(line)
        except Exception:
            pass

    async def check_log_for_active_node(line: str) -> None:
        if "[ACTIVE_NODE]" in line:
            return
        m = HTTP_LOG_PATH_RE.search(line)
        if not m:
            return
        req_path = (m.group(1) or m.group(2) or "").strip()
        if not req_path:
            return
        # Match exact route or longest prefix in route_map
        matched_file = route_map.get(req_path)
        if not matched_file:
            for route_prefix, rel_file in route_map.items():
                if route_prefix != "/" and req_path.startswith(route_prefix):
                    matched_file = rel_file
                    break
        if matched_file:
            await emit_log(f"[ACTIVE_NODE] {matched_file}\r\n")

    async def _run_step_cmd(cmd: List[str], cwd: Path, env: Dict[str, str], stderr_acc: List[str]) -> int:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            text = raw_line.decode("utf-8", errors="replace")
            stderr_acc.append(text)
            await emit_log(text)
        return await proc.wait()

    async def execute_plan(plan: RunPlan) -> PlanExecResult:
        if not plan.runnable:
            await emit_log(f"[RD_PLANNER] Project marked non-runnable ({plan.reason or plan.reasoning})\r\n")
            return PlanExecResult(ok=False, log=plan.reason or plan.reasoning or "Project marked non-runnable.")

        ordered_services: List[ServiceSpec] = topo_order(plan)
        allocated_ports: Set[int] = set()
        service_ports: Dict[str, int] = {}
        service_urls: Dict[str, str] = {}
        stderr_log: List[str] = []
        host = host_ip

        for svc in ordered_services:
            if not svc.start or svc.role in ("mobile", "library"):
                await emit_log(f"[RD_SKIP] Skipping companion target '{svc.name}' (role={svc.role})\r\n")
                continue

            port = _find_free_port(base_port, allocated_ports)
            allocated_ports.add(port)
            service_ports[svc.name] = port
            service_urls[svc.name] = f"http://{host}:{port}"

        for svc in ordered_services:
            if not svc.start or svc.role in ("mobile", "library"):
                continue

            svc_cwd = (ws_path / svc.cwd).resolve() if svc.cwd and svc.cwd != "." else ws_path
            svc_cwd.mkdir(parents=True, exist_ok=True)
            port = service_ports[svc.name]

            # Build environment with placeholders resolved & multi-service frontend wiring
            run_env = os.environ.copy()
            run_env.update(
                {
                    "PORT": str(port),
                    "RD_HOST_PORT": str(port),
                    "HOST": host,
                    "BROWSER": "none",
                    "CI": "true",
                    "PYTHONUNBUFFERED": "1",
                }
            )
            for k, v in svc.env.items():
                run_env[k] = _substitute_placeholders(str(v), host, port, service_urls)

            if svc.role == "frontend":
                backend_url = service_urls.get("api") or next(
                    (u for n, u in service_urls.items() if n != svc.name), None
                )
                if backend_url:
                    run_env.setdefault("VITE_API_URL", backend_url)
                    run_env.setdefault("VITE_API_BASE_URL", backend_url)
                    run_env.setdefault("REACT_APP_API_URL", backend_url)
                    run_env.setdefault("NEXT_PUBLIC_API_URL", backend_url)

            # 1. Run install commands
            for icmd in svc.install:
                resolved_icmd = [
                    _substitute_placeholders(tok, host, port, service_urls)
                    for tok in _normalize_service_cmd(ws_path, svc_cwd, icmd)
                ]
                await emit_log(f"[RD_INSTALL] ({svc.name}) $ {' '.join(resolved_icmd)}\r\n")
                rc = await _run_step_cmd(resolved_icmd, svc_cwd, run_env, stderr_log)
                if rc != 0:
                    return PlanExecResult(ok=False, log="".join(stderr_log[-80:]), failed_service=svc.name, exit_code=rc)

            # 2. Run build commands
            for bcmd in svc.build:
                resolved_bcmd = [
                    _substitute_placeholders(tok, host, port, service_urls)
                    for tok in _normalize_service_cmd(ws_path, svc_cwd, bcmd)
                ]
                await emit_log(f"[RD_BUILD] ({svc.name}) $ {' '.join(resolved_bcmd)}\r\n")
                rc = await _run_step_cmd(resolved_bcmd, svc_cwd, run_env, stderr_log)
                if rc != 0:
                    return PlanExecResult(ok=False, log="".join(stderr_log[-80:]), failed_service=svc.name, exit_code=rc)

            # 3. Spawn service daemon
            start_cmd = [
                _substitute_placeholders(tok, host, port, service_urls)
                for tok in _normalize_service_cmd(ws_path, svc_cwd, svc.start)
            ]
            await emit_log(f"[RD_START] ({svc.name}) $ {' '.join(start_cmd)}\r\n")

            proc = await asyncio.create_subprocess_exec(
                *start_cmd,
                cwd=str(svc_cwd),
                env=run_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if register_process is not None:
                register_process(pid, proc)
            elif pid and isinstance(ACTIVE_LOCAL_PROCESSES, dict):
                ACTIVE_LOCAL_PROCESSES[pid] = proc

            # Stream daemon output in background and watch for HTTP routes -> [ACTIVE_NODE]
            async def _stream_daemon_stdout(p: asyncio.subprocess.Process) -> None:
                assert p.stdout is not None
                async for raw in p.stdout:
                    line = raw.decode("utf-8", errors="replace")
                    stderr_log.append(line)
                    await emit_log(line)
                    await check_log_for_active_node(line)

            asyncio.create_task(_stream_daemon_stdout(proc))

            # 4. Readiness Probe + OS Socket Port Adoption
            probe = svc.readiness
            probe_path = probe.path if (probe and probe.path) else "/"
            probe_type = probe.type if probe else "tcp"
            ready = False
            actual_port = port

            for _ in range(60):  # Up to 30 seconds (60 * 0.5s)
                if proc.returncode is not None:
                    # Process exited prematurely!
                    await asyncio.sleep(0.2)
                    return PlanExecResult(
                        ok=False,
                        log="".join(stderr_log[-100:]),
                        failed_service=svc.name,
                        exit_code=proc.returncode,
                    )

                actual_port = _detect_actual_listening_port(proc.pid, port)
                if probe_type == "http":
                    target_url = f"http://{host}:{actual_port}{probe_path}"
                    if await _probe_http(target_url):
                        ready = True
                        break
                else:
                    if await _probe_tcp(host, actual_port):
                        ready = True
                        break

                await asyncio.sleep(0.5)

            if not ready and probe_type != "none":
                return PlanExecResult(
                    ok=False,
                    log="".join(stderr_log[-100:]) or f"Readiness timeout on {svc.name}",
                    failed_service=svc.name,
                    exit_code=proc.returncode or 1,
                )

            # Update resolved service URL if the child process adopted a different port
            service_ports[svc.name] = actual_port
            service_urls[svc.name] = f"http://{host}:{actual_port}"

            if svc.name == plan.entry_service or len(ordered_services) == 1:
                live_url = f"http://{host}:{actual_port}{probe_path if probe_type == 'http' else ''}"
                await emit_log(
                    f"\r\n[LIVE_PREVIEW_URL] {live_url}\r\n"
                    f"============================================================\r\n"
                    f">> Project is running live at: {live_url}\r\n"
                    f"============================================================\r\n\r\n"
                )

        return PlanExecResult(ok=True, log="All services running and healthy.")

    return execute_plan
