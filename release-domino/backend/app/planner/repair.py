from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from app.planner.schema import RunPlan, ServiceSpec
except ImportError:
    from schema import RunPlan, ServiceSpec

# Canonical mapping of Python import names to PyPI package names
PY_IMPORT_TO_PKG: Dict[str, str] = {
    "cv2": "opencv-python-headless",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "jose": "python-jose[cryptography]",
    "passlib": "passlib[bcrypt]",
    "multipart": "python-multipart",
    "pydantic_settings": "pydantic-settings",
    "email_validator": "email-validator",
    "sqlalchemy": "SQLAlchemy",
    "psycopg2": "psycopg2-binary",
    "MySQLdb": "mysqlclient",
    "fitz": "PyMuPDF",
    "dateutil": "python-dateutil",
    "google": "google-generativeai",
}

SAFE_ENV_DEFAULTS: Dict[str, str] = {
    "DATABASE_URL": "sqlite:///./sandbox.db",
    "SQLALCHEMY_DATABASE_URI": "sqlite:///./sandbox.db",
    "SECRET_KEY": "rd-sandbox-secret-key-not-for-prod",
    "JWT_SECRET": "rd-sandbox-jwt-secret-key",
    "JWT_SECRET_KEY": "rd-sandbox-jwt-secret-key",
    "OPENAI_API_KEY": "sk-sandbox-placeholder",
    "CORS_ORIGINS": "*",
    "ALLOWED_HOSTS": "*",
    "DEBUG": "true",
}

RE_PY_MISSING_MOD = re.compile(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]")
RE_PY_REL_IMPORT = re.compile(r"ImportError:\s+attempted relative import with no known parent package")
RE_NODE_MISSING_MOD = re.compile(r"Cannot find module ['\"]([^'\"./][^'\"]*)['\"]")
RE_NPM_ERESOLVE = re.compile(r"ERESOLVE unable to resolve dependency tree|peer dep missing", re.IGNORECASE)
RE_PORT_IN_USE = re.compile(
    r"EADDRINUSE|Address already in use|Errno 98|Errno 48|Errno 10048|port is already allocated",
    re.IGNORECASE,
)
RE_KEY_ERROR = re.compile(r"KeyError:\s*['\"]([A-Z0-9_]{2,})['\"]")
RE_PYDANTIC_ENV = re.compile(r"([A-Z0-9_]{3,})\s*\n\s*Field required", re.MULTILINE)
RE_SQLITE_NO_TABLE = re.compile(r"OperationalError:\s*no such table", re.IGNORECASE)


@dataclass
class RepairOutcome:
    repaired: bool
    plan: RunPlan
    action: str
    reason: str


@dataclass
class RuleFix:
    changed: bool = False
    reallocate_port: bool = False
    needs_services: List[str] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)


def _target_service(plan: RunPlan, failed_service: Optional[str]) -> Optional[ServiceSpec]:
    if failed_service:
        for s in plan.services:
            if s.name == failed_service:
                return s
    if plan.entry_service:
        for s in plan.services:
            if s.name == plan.entry_service:
                return s
    runnable = [s for s in plan.services if s.start]
    return runnable[0] if runnable else None


def attempt_deterministic_repair(
    plan: RunPlan,
    stderr_text: str,
    failed_service: Optional[str] = None,
) -> RepairOutcome:
    """
    Tier-1 0ms deterministic self-healing engine.
    Inspects crash stderr/stdout and mutates a deep copy of `RunPlan` if a known signature matches.
    """
    new_plan = copy.deepcopy(plan)
    svc = _target_service(new_plan, failed_service)
    if svc is None:
        return RepairOutcome(False, plan, "none", "No runnable service to repair.")

    # 1. Port Conflict (EADDRINUSE / Errno 98 / Errno 10048)
    if RE_PORT_IN_USE.search(stderr_text):
        svc.env["RD_FORCE_REALLOCATE_PORT"] = "1"
        return RepairOutcome(
            repaired=True,
            plan=new_plan,
            action="reallocate_port",
            reason=f"Detected port conflict on service '{svc.name}'; requesting fresh host port.",
        )

    # 2. Missing Python Package (ModuleNotFoundError)
    m_py = RE_PY_MISSING_MOD.search(stderr_text)
    if m_py:
        missing_import = m_py.group(1).split(".")[0]
        pkg_name = PY_IMPORT_TO_PKG.get(missing_import, missing_import)
        install_cmd = ["uv", "pip", "install", pkg_name]
        if install_cmd not in svc.install:
            svc.install.append(install_cmd)
            return RepairOutcome(
                repaired=True,
                plan=new_plan,
                action=f"install_py_pkg:{pkg_name}",
                reason=f"Mapped missing Python import '{missing_import}' -> '{pkg_name}'.",
            )

    # 3. Python Relative Import Error
    if RE_PY_REL_IMPORT.search(stderr_text):
        svc.env["PYTHONPATH"] = "."
        for idx, tok in enumerate(svc.start):
            if tok.endswith(".py") and tok != "_rd_web_wrapper.py" and "/" in tok.replace("\\", "/"):
                mod_name = tok.replace("\\", "/")[:-3].replace("/", ".")
                svc.start[idx] = "-m"
                svc.start.insert(idx + 1, mod_name)
                return RepairOutcome(
                    repaired=True,
                    plan=new_plan,
                    action=f"py_module_mode:{mod_name}",
                    reason="Converted script path to Python `-m` package execution to resolve relative imports.",
                )

    # 4. NPM Peer Dependency Conflict (ERESOLVE)
    if RE_NPM_ERESOLVE.search(stderr_text):
        mutated = False
        for cmd in svc.install:
            if cmd and cmd[0] == "npm" and "install" in cmd and "--legacy-peer-deps" not in cmd:
                cmd.append("--legacy-peer-deps")
                mutated = True
        if mutated:
            return RepairOutcome(
                repaired=True,
                plan=new_plan,
                action="npm_legacy_peer_deps",
                reason="Added `--legacy-peer-deps` to resolve NPM dependency tree conflict.",
            )

    # 5. Missing Node.js Package (Cannot find module '<pkg>')
    m_node = RE_NODE_MISSING_MOD.search(stderr_text)
    if m_node:
        raw_mod = m_node.group(1)
        parts = raw_mod.split("/")
        pkg_name = "/".join(parts[:2]) if raw_mod.startswith("@") and len(parts) >= 2 else parts[0]
        install_cmd = ["npm", "install", pkg_name, "--legacy-peer-deps"]
        if install_cmd not in svc.install:
            svc.install.append(install_cmd)
            return RepairOutcome(
                repaired=True,
                plan=new_plan,
                action=f"install_node_pkg:{pkg_name}",
                reason=f"Added missing Node dependency '{pkg_name}'.",
            )

    # 6. Missing Environment Variable (KeyError / Pydantic Settings Field required)
    m_env = RE_KEY_ERROR.search(stderr_text) or RE_PYDANTIC_ENV.search(stderr_text)
    if m_env:
        env_key = m_env.group(1)
        if env_key not in svc.env:
            default_val = SAFE_ENV_DEFAULTS.get(
                env_key,
                "sqlite:///./sandbox.db" if "DB" in env_key or "DATABASE" in env_key else "sandbox-default-value",
            )
            svc.env[env_key] = default_val
            return RepairOutcome(
                repaired=True,
                plan=new_plan,
                action=f"inject_env:{env_key}",
                reason=f"Injected safe sandbox default for missing environment key '{env_key}'.",
            )

    # 7. Unmigrated Database Tables (OperationalError: no such table)
    if RE_SQLITE_NO_TABLE.search(stderr_text):
        migrate_cmd = ["python", "manage.py", "migrate", "--noinput"]
        if migrate_cmd not in svc.build:
            svc.build.insert(0, migrate_cmd)
            return RepairOutcome(
                repaired=True,
                plan=new_plan,
                action="prepend_db_migrate",
                reason="Prepended database migration step before service start.",
            )

    return RepairOutcome(False, plan, "none", "No deterministic repair rule matched stderr.")


def try_rules(plan: RunPlan, failed_service: str, log: str) -> RuleFix:
    """Mutates `plan` in place for callers (engine.py, test_planner.py)."""
    fix = RuleFix()
    svc = _target_service(plan, failed_service)
    if not svc:
        return fix

    # 1. Port in use
    if RE_PORT_IN_USE.search(log):
        fix.reallocate_port = True
        fix.rules.append("port-in-use")
        fix.changed = True

    # 2. Python missing module
    m_py = RE_PY_MISSING_MOD.search(log)
    if m_py:
        missing = m_py.group(1).split(".")[0]
        pkg = PY_IMPORT_TO_PKG.get(missing, missing)
        cmd = ["uv", "pip", "install", pkg]
        if cmd not in svc.install:
            svc.install.append(cmd)
            fix.rules.append(f"py-missing-module:{pkg}")
            fix.changed = True

    # 3. Python relative import
    if RE_PY_REL_IMPORT.search(log):
        svc.env["PYTHONPATH"] = "."
        for idx, tok in enumerate(svc.start):
            if tok.endswith(".py") and tok != "_rd_web_wrapper.py" and "/" in tok.replace("\\", "/"):
                mod_name = tok.replace("\\", "/")[:-3].replace("/", ".")
                svc.start[idx] = "-m"
                svc.start.insert(idx + 1, mod_name)
                fix.rules.append(f"py-module-mode:{mod_name}")
                fix.changed = True
                break

    # 4. Node missing module
    m_node = RE_NODE_MISSING_MOD.search(log)
    if m_node:
        raw_mod = m_node.group(1)
        parts = raw_mod.split("/")
        pkg_name = "/".join(parts[:2]) if raw_mod.startswith("@") and len(parts) >= 2 else parts[0]
        cmd = ["npm", "install", pkg_name, "--legacy-peer-deps"]
        if cmd not in svc.install:
            svc.install.append(cmd)
            fix.rules.append(f"node-missing-module:{pkg_name}")
            fix.changed = True

    # 5. NPM ERESOLVE
    if RE_NPM_ERESOLVE.search(log):
        for icmd in svc.install:
            if icmd and icmd[0] == "npm" and "install" in icmd and "--legacy-peer-deps" not in icmd:
                icmd.append("--legacy-peer-deps")
                fix.rules.append("npm-legacy-peer-deps")
                fix.changed = True

    # 6. Missing environment variable
    m_env = RE_KEY_ERROR.search(log) or RE_PYDANTIC_ENV.search(log)
    if m_env:
        key = m_env.group(1)
        if key not in svc.env:
            val = SAFE_ENV_DEFAULTS.get(key, "sandbox-dummy-secret-0000" if "SECRET" in key else "sandbox-default")
            svc.env[key] = val
            fix.rules.append(f"env:{key}")
            fix.changed = True

    # 7. Unmigrated database table
    if RE_SQLITE_NO_TABLE.search(log):
        migrate_cmd = ["python", "manage.py", "migrate", "--noinput"]
        if migrate_cmd not in svc.build:
            svc.build.insert(0, migrate_cmd)
            fix.rules.append("db-migrate")
            fix.changed = True

    return fix
