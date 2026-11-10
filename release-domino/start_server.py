#!/usr/bin/env python3
"""
Release Domino — Quick Start Server (Person 2)
Automatically detects port conflicts and Windows [WinError 10013] socket permission restrictions,
falling back to the next available port (e.g. 8001, 8080) automatically.

Run from anywhere:
    python start_server.py            # checks 8000 -> falls back to next open port if restricted
    python start_server.py 8080       # custom port
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR / "backend"
VENV_PYTHON = SCRIPT_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

os.environ.setdefault("RD_ALLOW_LOCAL_FALLBACK", "1")
os.environ.setdefault("RD_FORCE_LOCAL_RUNNER", "1")


def is_port_bindable(host: str, p: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, p))
            return True
    except OSError:
        return False


def find_free_port(preferred: int, host: str = "127.0.0.1") -> int:
    if is_port_bindable(host, preferred):
        return preferred
    candidates = list(range(preferred + 1, preferred + 50)) + [8080, 8081, 8088, 5000, 3000]
    for cand in candidates:
        if is_port_bindable(host, cand):
            return cand
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


req_port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000

# Try to terminate any stale process holding the requested port on Windows
if os.name == "nt":
    try:
        netstat = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        for line in (netstat.stdout or "").splitlines():
            if f":{req_port_arg} " in line and "LISTENING" in line:
                pid_str = line.strip().split()[-1]
                if pid_str.isdigit() and int(pid_str) != os.getpid():
                    print(f"[Release Domino] Stopping previous server on port {req_port_arg} (PID {pid_str})...")
                    subprocess.run(["taskkill", "/F", "/PID", pid_str], capture_output=True, check=False)
    except Exception:
        pass

active_port = find_free_port(req_port_arg, "127.0.0.1")
if active_port != req_port_arg:
    print(f"[Release Domino] Notice: Port {req_port_arg} is reserved or in use ([WinError 10013]).")
    print(f"[Release Domino] Automatically selected next available port: {active_port}")

print(f"[Release Domino] Starting Person 2 server on http://127.0.0.1:{active_port}")
print(f"[Release Domino] Using Python: {VENV_PYTHON}")
print(f"[Release Domino] Working dir: {BACKEND_DIR}")
print()

for attempt in range(5):
    try:
        subprocess.run(
            [
                str(VENV_PYTHON), "-m", "uvicorn",
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", str(active_port),
                "--reload",
            ],
            cwd=str(BACKEND_DIR),
            check=True,
        )
        break
    except subprocess.CalledProcessError as e:
        if e.returncode == 3 and attempt < 4:
            next_port = find_free_port(active_port + 1, "127.0.0.1")
            print(f"\n[Release Domino] Port {active_port} failed to bind (exit code 3). Retrying on port {next_port}...")
            active_port = next_port
            continue
        print(f"\n[Release Domino] Server exited with code {e.returncode}")
        break
    except KeyboardInterrupt:
        print("\n[Release Domino] Server stopped.")
        break
