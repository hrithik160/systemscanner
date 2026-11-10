from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Set, Tuple

try:
    from app.planner.schema import RunPlan, Service, topo_order
except ImportError:
    from schema import RunPlan, Service, topo_order

ALLOWED_BINARIES: Set[str] = {
    "python",
    "python3",
    "uv",
    "pip",
    "uvicorn",
    "gunicorn",
    "streamlit",
    "flask",
    "django-admin",
    "node",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "vite",
    "next",
    "go",
    "cargo",
    "mvn",
    "gradle",
    "php",
    "ruby",
    "bundle",
    "dotnet",
    "make",
    "pytest",
}

FORBIDDEN_SHELL_TOKENS: Set[str] = {";", "&&", "||", "|", "`", "$(", ">", ">>", "<"}
FORBIDDEN_COMMANDS: Set[str] = {"rm", "del", "format", "shutdown"}
FORBIDDEN_ENV_KEYS: Set[str] = {"NODE_OPTIONS", "PYTHONPATH"}
KNOWN_PLACEHOLDERS: Set[str] = {"{HOST}", "{PORT}"}


def _validate_cmd_list(cmd: List[str], context: str) -> List[str]:
    errors: List[str] = []
    if not cmd:
        return errors

    binary = cmd[0].strip()
    if binary not in ALLOWED_BINARIES and not binary.startswith(("./", ".\\", "bin/")):
        errors.append(f"{context}: binary '{binary}' is not allowlisted")

    for idx, token in enumerate(cmd):
        for bad in (";", "&&", "||", "`", "$("):
            if bad in token:
                errors.append(f"{context}: shell metacharacter in '{token}'")
                break
        if token in FORBIDDEN_COMMANDS:
            errors.append(f"{context}: dangerous command '{token}' is not permitted")

        if token in ("-c", "-e", "/c", "--eval") and idx > 0 and binary in ("python", "python3", "node"):
            errors.append(f"{context}: inline code flag {token} is not allowed")

        if token.startswith("git+") or token.startswith("http://") or token.startswith("https://"):
            errors.append(f"{context}: install source/flag '{token}' is not allowed")

        # Unknown placeholders {FOO}
        for ph in ("{SECRET}", "{KEY}", "{PASSWORD}", "{TOKEN}"):
            if ph in token:
                errors.append(f"{context}: unknown placeholder {ph}")

    return errors


def validate_plan(plan: RunPlan, workspace: str | Path | None = None) -> list[str]:
    """Validates plan against security and sandbox policies. Returns empty list if clean."""
    errors: list[str] = []

    if not plan.runnable:
        for svc in plan.services:
            if svc.start:
                errors.append(f"Plan is marked runnable=False, but service '{svc.name}' has a start command.")
        return errors

    if not plan.services:
        errors.append("Plan is marked runnable=True, but contains no services.")
        return errors

    svc_names = {s.name for s in plan.services}
    if plan.entry_service and plan.entry_service not in svc_names:
        errors.append(f"entry_service '{plan.entry_service}' does not match any declared service {svc_names}.")

    # Cycle check
    visited: set[str] = set()
    stack: set[str] = set()
    by_name = {s.name: s for s in plan.services}

    def has_cycle(name: str) -> bool:
        visited.add(name)
        stack.add(name)
        for dep in by_name.get(name, Service(name=name, role="backend")).depends_on:
            if dep not in visited:
                if has_cycle(dep):
                    return True
            elif dep in stack:
                return True
        stack.remove(name)
        return False

    for s in plan.services:
        if s.name not in visited:
            if has_cycle(s.name):
                errors.append("cycle in service dependencies")
                break

    for svc in plan.services:
        norm_cwd = svc.cwd.replace("\\", "/").split("/")
        if ".." in norm_cwd:
            errors.append(f"{svc.name}: cwd '{svc.cwd}' escapes the workspace")

        if svc.role == "mobile" and svc.start:
            errors.append(f"[{svc.name}] Mobile service (role='mobile') must not define a web start command.")

        for k, v in svc.env.items():
            if k in FORBIDDEN_ENV_KEYS:
                errors.append(f"{svc.name}.env: '{k}' is set by the sandbox, not by plans")
            if any(p in v for p in ("/etc/", "/var/", "C:\\Windows", "C:\\Users")):
                errors.append(f"{svc.name}.env.{k}: references a host path")

        for idx, icmd in enumerate(svc.install):
            errors.extend(_validate_cmd_list(icmd, f"{svc.name}.install[{idx}]"))

        for idx, bcmd in enumerate(svc.build):
            errors.extend(_validate_cmd_list(bcmd, f"{svc.name}.build[{idx}]"))

        if svc.start:
            errors.extend(_validate_cmd_list(svc.start, f"{svc.name}.start"))

        for dep in svc.depends_on:
            if dep not in svc_names:
                errors.append(f"[{svc.name}] depends_on references unknown service '{dep}'.")
            if dep == svc.name:
                errors.append(f"[{svc.name}] Service cannot depend on itself.")

    return errors


def validate_run_plan(plan: RunPlan) -> Tuple[bool, List[str]]:
    """Tuple contract for universal planner validation."""
    errs = validate_plan(plan)
    return (len(errs) == 0, errs)
