"""
Person 3 Core Configuration (backend/app/config.py)
Loads environment settings from `.env` or environment variables with safe defaults.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5-coder:3b")

WORKSPACES_DIR: Path = Path(
    os.getenv("RD_WORKSPACES_DIR", str(Path(tempfile.gettempdir()) / "rd_sandbox_projects"))
)
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

DEMO_REPO_PATH: Path = REPO_ROOT / "demo" / "demo_shop_repo"
SHARED_MOCK_DIR: Path = REPO_ROOT / "shared" / "mock"
USE_MOCK: bool = os.getenv("USE_MOCK", "0").lower() in ("1", "true", "yes")
