"""Deterministic architecture, framework, runtime, and styling detector + 3-sentence LLM summary (Task L7)."""

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.llm import client
from app.llm.prompts import ARCHITECTURE_SUMMARY_PROMPT

# Known libraries -> (Display Name, Category: 'stack' or 'infra')
KNOWN_PACKAGES: dict[str, tuple[str, str]] = {
    "fastapi": ("FastAPI", "stack"),
    "flask": ("Flask", "stack"),
    "django": ("Django", "stack"),
    "streamlit": ("Streamlit", "stack"),
    "express": ("Express", "stack"),
    "react": ("React", "stack"),
    "vite": ("Vite", "stack"),
    "next": ("Next.js", "stack"),
    "vue": ("Vue", "stack"),
    "tailwindcss": ("Tailwind CSS", "stack"),
    "pydantic": ("Pydantic", "stack"),
    "redis": ("Redis", "infra"),
    "aioredis": ("Redis", "infra"),
    "psycopg2": ("PostgreSQL", "infra"),
    "psycopg2-binary": ("PostgreSQL", "infra"),
    "asyncpg": ("PostgreSQL", "infra"),
    "sqlalchemy": ("SQL Database", "infra"),
    "sqlite3": ("SQLite", "infra"),
    "pymongo": ("MongoDB", "infra"),
    "motor": ("MongoDB", "infra"),
    "mongoose": ("MongoDB", "infra"),
    "boto3": ("AWS S3/Cloud", "infra"),
    "celery": ("Celery Queue", "infra"),
    "kafka": ("Kafka", "infra"),
}

ENV_INFRA_HINTS: dict[str, str] = {
    "REDIS": "Redis",
    "POSTGRES": "PostgreSQL",
    "DATABASE_URL": "SQL Database",
    "DB_": "SQL Database",
    "MONGO": "MongoDB",
}


class NodeInfraLink(BaseModel):
    """Represents a connection between a code node and an infrastructure service."""
    node_id: str
    infra: str
    reason: str = "Imports or references service"


class ArchitectureResult(BaseModel):
    """Contract return shape for GET /api/architecture/{pid}."""
    stack: list[str] = Field(default_factory=list)
    infra: list[str] = Field(default_factory=list)
    node_infra_links: list[NodeInfraLink] = Field(default_factory=list)
    summary: str = ""
    framework: str = "Python"
    run_command: str = "python main.py"
    entry_point: str = "main.py"
    port: int = 5050
    styling: str = "Plain CSS"


class _SummarySchema(BaseModel):
    summary: str


def _scan_requirements_txt(content: str, stack: set[str], infra: set[str]) -> None:
    for raw_line in content.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        pkg = re.split(r"[=<>!~\[\s]", line)[0].strip()
        if pkg in KNOWN_PACKAGES:
            label, kind = KNOWN_PACKAGES[pkg]
            (stack if kind == "stack" else infra).add(label)


def _scan_package_json(content: str, stack: set[str], infra: set[str]) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except Exception:
        return {}
    deps = {}
    deps.update(data.get("dependencies", {}) or {})
    deps.update(data.get("devDependencies", {}) or {})
    for pkg in deps:
        clean = pkg.lower().lstrip("@").split("/")[-1]
        if clean in KNOWN_PACKAGES:
            label, kind = KNOWN_PACKAGES[clean]
            (stack if kind == "stack" else infra).add(label)
    return data


def _scan_docker_compose(content: str, infra: set[str]) -> None:
    lowered = content.lower()
    if "redis" in lowered:
        infra.add("Redis")
    if "postgres" in lowered:
        infra.add("PostgreSQL")
    if "mongo" in lowered:
        infra.add("MongoDB")
    if "mysql" in lowered or "mariadb" in lowered:
        infra.add("MySQL")


def _scan_env_keys(content: str, infra: set[str]) -> None:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip().upper()
        for hint, label in ENV_INFRA_HINTS.items():
            if hint in key:
                infra.add(label)


def _detect_styling_architecture(
    project_path: Path | None,
    nodes: list[dict[str, Any]],
    codes: dict[str, str],
) -> str:
    """Detect whether the project uses Tailwind, CSS Modules, SCSS, Styled Components, or Plain CSS."""
    styles_found: list[str] = []
    if project_path and project_path.exists():
        if any(project_path.rglob("tailwind.config.*")):
            styles_found.append("Tailwind CSS")
        if any(project_path.rglob("*.module.css")) or any(project_path.rglob("*.module.scss")):
            styles_found.append("CSS Modules")
        if any(project_path.rglob("*.scss")) or any(project_path.rglob("*.sass")):
            styles_found.append("SCSS/SASS")
        if any(project_path.rglob("*.css")):
            styles_found.append("Plain CSS")

    combined_code = "\n".join(codes.values())
    if "styled-components" in combined_code or "@emotion/styled" in combined_code:
        styles_found.append("Styled Components")
    if ".module.css" in combined_code and "CSS Modules" not in styles_found:
        styles_found.append("CSS Modules")
    if "tailwind" in combined_code.lower() and "Tailwind CSS" not in styles_found:
        styles_found.append("Tailwind CSS")

    return ", ".join(dict.fromkeys(styles_found)) if styles_found else "Standard / CLI"


def _scan_node_code_and_imports(
    node_id: str,
    code: str,
    deps: list[str],
    stack: set[str],
    infra: set[str],
    links: list[NodeInfraLink],
) -> None:
    combined_tokens = set(
        t.lower()
        for t in deps + re.findall(r"(?:import|from|require)\s*\(?['\"]?([a-zA-Z0-9_.-]+)", code)
    )
    stem = Path(node_id).stem.lower()
    if "redis" in stem:
        combined_tokens.add("redis")

    seen_for_node: set[str] = set()
    for token in combined_tokens:
        base_pkg = token.split(".")[0]
        if base_pkg in KNOWN_PACKAGES:
            label, kind = KNOWN_PACKAGES[base_pkg]
            if kind == "stack":
                stack.add(label)
            else:
                infra.add(label)
                if label not in seen_for_node:
                    seen_for_node.add(label)
                    links.append(
                        NodeInfraLink(
                            node_id=node_id,
                            infra=label,
                            reason=f"Imports or references {base_pkg}",
                        )
                    )


def _build_fallback_arch_summary(
    stack: list[str],
    infra: list[str],
    links: list[NodeInfraLink],
    framework: str = "Python",
    styling: str = "Standard",
) -> _SummarySchema:
    stack_str = ", ".join(stack) if stack else framework
    infra_str = ", ".join(infra) if infra else "local in-memory state"
    return _SummarySchema(
        summary=(
            f"This project is built using {stack_str} ({framework} runtime with {styling} styling). "
            f"It integrates with {infra_str} for backing services and data persistence. "
            f"A total of {len(links)} module-to-infrastructure connection(s) were detected across the codebase."
        )
    )


async def detect_architecture(
    nodes: list[dict[str, Any]],
    node_codes: dict[str, str] | None = None,
    project_path: str | Path | None = None,
) -> ArchitectureResult:
    """Deterministically detect stack, framework, run command, styling, infrastructure, and 3-sentence LLM summary."""
    stack: set[str] = set()
    infra: set[str] = set()
    links: list[NodeInfraLink] = []
    codes = node_codes or {}
    root: Path | None = Path(project_path) if project_path is not None else None

    pkg_json_data: dict[str, Any] = {}
    if root is not None and root.exists():
        req_file = root / "requirements.txt"
        if req_file.exists():
            _scan_requirements_txt(req_file.read_text(encoding="utf-8", errors="ignore"), stack, infra)

        pkg_file = root / "package.json"
        if pkg_file.exists():
            pkg_json_data = _scan_package_json(pkg_file.read_text(encoding="utf-8", errors="ignore"), stack, infra)

        for dc_name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
            dc_file = root / dc_name
            if dc_file.exists():
                _scan_docker_compose(dc_file.read_text(encoding="utf-8", errors="ignore"), infra)

        for env_name in (".env", ".env.example"):
            env_file = root / env_name
            if env_file.exists():
                _scan_env_keys(env_file.read_text(encoding="utf-8", errors="ignore"), infra)

    for node in nodes:
        nid = str(node.get("id", ""))
        kind = str(node.get("kind", ""))
        lang = str(node.get("lang", ""))
        if lang == "py":
            stack.add("Python")
        elif lang in ("ts", "js"):
            stack.add("TypeScript/JavaScript")

        if kind == "infra":
            label = str(node.get("label") or nid)
            infra.add(label)
            continue

        deps = list(node.get("deps", []) or node.get("dependencies", []) or [])
        code = codes.get(nid, "")
        _scan_node_code_and_imports(nid, code, deps, stack, infra, links)

    styling = _detect_styling_architecture(root, nodes, codes)
    if styling not in ("Standard / CLI", "Plain CSS"):
        stack.add(styling.split(",")[0].strip())

    # Determine framework, entry_point, run_command, and port
    framework = "Python"
    entry_point = "main.py"
    run_command = "python main.py"
    port = 5050

    if root is not None and root.exists():
        try:
            from app.runner.terminal import detect_project_runtime
            rt = detect_project_runtime(root)
            framework = rt.get("stack", "Python")
            cmd_list = rt.get("cmd_args", [])
            if len(cmd_list) >= 3 and cmd_list[1] == "_rd_web_wrapper.py":
                entry_point = cmd_list[2]
                run_command = f"python {entry_point}"
            elif cmd_list:
                run_command = " ".join(cmd_list)
            port = 5050 if rt.get("is_web", True) else 0
        except Exception:
            pass
    else:
        if "Vite" in stack and "React" in stack:
            framework = "Vite + React"
            entry_point = "src/main.tsx"
            run_command = "npm run dev"
        elif "FastAPI" in stack:
            framework = "FastAPI"
            entry_point = "app/main.py"
            run_command = "uvicorn app.main:app --port 5050"
        elif "Flask" in stack:
            framework = "Flask"
            entry_point = "app.py"
            run_command = "python app.py"
        elif "Express" in stack:
            framework = "Express"
            entry_point = "server.js"
            run_command = "node server.js"

    sorted_stack = sorted(stack)
    sorted_infra = sorted(infra)

    prompt = ARCHITECTURE_SUMMARY_PROMPT.format(
        stack=", ".join(sorted_stack) or "None detected",
        infra=", ".join(sorted_infra) or "None detected",
        links=json.dumps([lnk.model_dump() if hasattr(lnk, "model_dump") else lnk.dict() for lnk in links]),
    )

    llm_summary = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        schema=_SummarySchema,
        fallback_factory=lambda: _build_fallback_arch_summary(sorted_stack, sorted_infra, links, framework, styling),
    )

    return ArchitectureResult(
        stack=sorted_stack,
        infra=sorted_infra,
        node_infra_links=links,
        summary=llm_summary.summary,
        framework=framework,
        run_command=run_command,
        entry_point=entry_point,
        port=port,
        styling=styling,
    )