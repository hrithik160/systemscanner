from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from app.planner.facts import RepoFacts, gather_repo_facts
    from app.planner.schema import ReadinessProbe, RunPlan, ServiceSpec
except ImportError:
    from facts import RepoFacts, gather_repo_facts
    from schema import ReadinessProbe, RunPlan, ServiceSpec


@dataclass
class ServiceCandidate:
    name: str
    role: str  # "backend" | "frontend" | "fullstack" | "mobile" | "worker" | "library"
    cwd: str
    framework: str
    score: float
    runnable: bool = True
    install: List[List[str]] = field(default_factory=list)
    build: List[List[str]] = field(default_factory=list)
    start: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    readiness: Optional[ReadinessProbe] = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


Candidate = ServiceCandidate


PY_ENTRYPOINT_PRIORITY = (
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "api.py",
    "manage.py",
    "app/main.py",
    "src/main.py",
)


def _rel_to_cwd(file_rel_path: str, cwd: str) -> str:
    """
    Normalizes a repo-relative file path so it is relative to `cwd`.
    Fixes the bug where cwd='backend' and file='backend/app/main.py' doubled to 'backend/backend/app/main.py'.
    """
    norm_file = file_rel_path.replace("\\", "/").strip("/")
    norm_cwd = cwd.replace("\\", "/").strip("/")
    if not norm_cwd or norm_cwd == ".":
        return norm_file
    prefix = f"{norm_cwd}/"
    if norm_file.startswith(prefix):
        return norm_file[len(prefix) :]
    return norm_file


def _find_nearest_py_cwd_and_req(repo_path: Path, py_rel: str) -> tuple[str, Optional[str]]:
    """Finds the best working directory and requirements file for a Python entrypoint."""
    parts = Path(py_rel).parts
    # If inside backend/... or api/... or server/..., use that top-level service folder as cwd
    if len(parts) > 1 and parts[0] in ("backend", "api", "server", "services"):
        cwd = parts[0]
        if (repo_path / cwd / "requirements.txt").exists():
            return cwd, "requirements.txt"
        if (repo_path / "requirements.txt").exists():
            return cwd, "../requirements.txt"
        return cwd, None

    if (repo_path / "requirements.txt").exists():
        return ".", "requirements.txt"
    return ".", None


def extract_candidates_from_repo(repo_path: Path | str, facts: Optional[RepoFacts] = None) -> List[ServiceCandidate]:
    repo_path = Path(repo_path).resolve()
    if facts is None:
        facts = gather_repo_facts(repo_path)

    candidates: List[ServiceCandidate] = []

    # -------------------------------------------------------------------------
    # 1. Python Candidates (FastAPI, Flask, Django, Streamlit, Gradio)
    # -------------------------------------------------------------------------
    best_py_candidate: Optional[ServiceCandidate] = None

    # Sort files so canonical entrypoints come first
    def _py_rank(rel_f: str) -> tuple[int, int]:
        name = Path(rel_f).name
        for idx, cand in enumerate(PY_ENTRYPOINT_PRIORITY):
            if rel_f.endswith(cand) or name == cand:
                return (0, idx)
        return (1, len(Path(rel_f).parts))

    for py_file in sorted(facts.py_imports.keys(), key=_py_rank):
        if any(seg.startswith("test") or seg == "migrations" for seg in Path(py_file).parts):
            continue

        imps = set(facts.py_imports.get(py_file, []))
        cwd, req_file = _find_nearest_py_cwd_and_req(repo_path, py_file)
        entry_rel_to_cwd = _rel_to_cwd(py_file, cwd)

        install_cmds: List[List[str]] = []
        if req_file:
            install_cmds.append(["uv", "pip", "install", "-r", req_file])

        if "fastapi" in imps:
            best_py_candidate = ServiceCandidate(
                name="api",
                role="backend",
                cwd=cwd,
                framework="fastapi",
                score=0.95,
                runnable=True,
                install=install_cmds,
                start=["python", "_rd_web_wrapper.py", entry_rel_to_cwd],
                env={"PORT": "{PORT}", "HOST": "{HOST}", "PYTHONUNBUFFERED": "1"},
                readiness=ReadinessProbe(type="http", path="/docs"),
            )
            break
        elif "django" in imps or Path(py_file).name == "manage.py":
            manage_rel = _rel_to_cwd(py_file, cwd)
            best_py_candidate = ServiceCandidate(
                name="api",
                role="backend",
                cwd=cwd,
                framework="django",
                score=0.92,
                runnable=True,
                install=install_cmds,
                build=[["python", manage_rel, "migrate", "--noinput"]],
                start=["python", "_rd_web_wrapper.py", manage_rel, "runserver", "{HOST}:{PORT}", "--noreload"],
                env={"PORT": "{PORT}", "HOST": "{HOST}", "PYTHONUNBUFFERED": "1"},
                readiness=ReadinessProbe(type="http", path="/"),
            )
            break
        elif "streamlit" in imps:
            best_py_candidate = ServiceCandidate(
                name="web",
                role="fullstack",
                cwd=cwd,
                framework="streamlit",
                score=0.93,
                runnable=True,
                install=install_cmds,
                start=[
                    "streamlit",
                    "run",
                    entry_rel_to_cwd,
                    "--server.port",
                    "{PORT}",
                    "--server.address",
                    "{HOST}",
                    "--server.headless",
                    "true",
                ],
                env={"PORT": "{PORT}", "HOST": "{HOST}", "BROWSER": "none"},
                readiness=ReadinessProbe(type="http", path="/"),
            )
            break
        elif "gradio" in imps:
            best_py_candidate = ServiceCandidate(
                name="web",
                role="fullstack",
                cwd=cwd,
                framework="gradio",
                score=0.91,
                runnable=True,
                install=install_cmds,
                start=["python", "_rd_web_wrapper.py", entry_rel_to_cwd],
                env={
                    "PORT": "{PORT}",
                    "GRADIO_SERVER_PORT": "{PORT}",
                    "GRADIO_SERVER_NAME": "{HOST}",
                },
                readiness=ReadinessProbe(type="http", path="/"),
            )
            break
        elif "flask" in imps and best_py_candidate is None:
            best_py_candidate = ServiceCandidate(
                name="api",
                role="backend",
                cwd=cwd,
                framework="flask",
                score=0.90,
                runnable=True,
                install=install_cmds,
                start=["python", "_rd_web_wrapper.py", entry_rel_to_cwd],
                env={"PORT": "{PORT}", "HOST": "{HOST}", "FLASK_RUN_PORT": "{PORT}"},
                readiness=ReadinessProbe(type="http", path="/"),
            )

    if best_py_candidate is not None:
        candidates.append(best_py_candidate)

    # -------------------------------------------------------------------------
    # 2. Node.js / Frontend / Mobile Candidates
    # -------------------------------------------------------------------------
    for pkg_cwd, deps in facts.js_deps.items():
        has_html = facts.has_index_html.get(pkg_cwd, False)
        is_mobile = "expo" in deps or ("react-native" in deps and "react-native-web" not in deps and not has_html)

        if is_mobile:
            candidates.append(
                ServiceCandidate(
                    name="mobile",
                    role="mobile",
                    cwd=pkg_cwd,
                    framework="expo" if "expo" in deps else "react-native",
                    score=0.90,
                    runnable=False,
                )
            )
            continue

        if "next" in deps:
            candidates.append(
                ServiceCandidate(
                    name="web",
                    role="frontend",
                    cwd=pkg_cwd,
                    framework="nextjs",
                    score=0.92,
                    runnable=True,
                    install=[["npm", "install", "--legacy-peer-deps"]],
                    start=["npx", "next", "dev", "-p", "{PORT}", "-H", "{HOST}"],
                    env={"PORT": "{PORT}", "HOST": "{HOST}", "BROWSER": "none"},
                    readiness=ReadinessProbe(type="http", path="/"),
                )
            )
        elif "vite" in deps or (has_html and any(k in deps for k in ("react", "vue", "svelte"))):
            candidates.append(
                ServiceCandidate(
                    name="web",
                    role="frontend",
                    cwd=pkg_cwd,
                    framework="vite",
                    score=0.90,
                    runnable=True,
                    install=[["npm", "install", "--legacy-peer-deps"]],
                    start=["npx", "vite", "--host", "{HOST}", "--port", "{PORT}", "--strictPort"],
                    env={"PORT": "{PORT}", "HOST": "{HOST}", "BROWSER": "none"},
                    readiness=ReadinessProbe(type="http", path="/"),
                )
            )
        elif any(k in deps for k in ("express", "fastify", "koa", "@nestjs/core")):
            # Locate Node entry file
            pkg_json_path = (repo_path / pkg_cwd / "package.json").resolve()
            entry_js = "index.js"
            try:
                pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8", errors="ignore"))
                entry_js = pkg_data.get("main") or "index.js"
            except Exception:
                pass
            if not (repo_path / pkg_cwd / entry_js).exists():
                for fallback_js in ("server.js", "app.js", "src/index.js", "src/server.js"):
                    if (repo_path / pkg_cwd / fallback_js).exists():
                        entry_js = fallback_js
                        break

            candidates.append(
                ServiceCandidate(
                    name="api" if not any(c.name == "api" for c in candidates) else "node_api",
                    role="backend",
                    cwd=pkg_cwd,
                    framework="express",
                    score=0.88,
                    runnable=True,
                    install=[["npm", "install", "--legacy-peer-deps"]],
                    start=["node", entry_js],
                    env={"PORT": "{PORT}", "HOST": "{HOST}"},
                    readiness=ReadinessProbe(type="tcp"),
                )
            )

    # -------------------------------------------------------------------------
    # 3. Go / Rust / Java Spring Boot Candidates
    # -------------------------------------------------------------------------
    for rel_manifest in facts.manifests:
        m_path = Path(rel_manifest)
        m_cwd = "." if str(m_path.parent) == "." else m_path.parent.as_posix()
        if m_path.name == "go.mod":
            candidates.append(
                ServiceCandidate(
                    name="api",
                    role="backend",
                    cwd=m_cwd,
                    framework="go",
                    score=0.88,
                    runnable=True,
                    start=["go", "run", "."],
                    env={"PORT": "{PORT}", "HOST": "{HOST}"},
                    readiness=ReadinessProbe(type="tcp"),
                )
            )
        elif m_path.name == "Cargo.toml":
            candidates.append(
                ServiceCandidate(
                    name="api",
                    role="backend",
                    cwd=m_cwd,
                    framework="rust",
                    score=0.86,
                    runnable=True,
                    start=["cargo", "run"],
                    env={"PORT": "{PORT}", "ROCKET_PORT": "{PORT}", "HOST": "{HOST}"},
                    readiness=ReadinessProbe(type="tcp"),
                )
            )
        elif m_path.name == "pom.xml":
            candidates.append(
                ServiceCandidate(
                    name="api",
                    role="backend",
                    cwd=m_cwd,
                    framework="spring-boot",
                    score=0.86,
                    runnable=True,
                    start=["mvn", "spring-boot:run", "-Dspring-boot.run.arguments=--server.port={PORT}"],
                    env={"PORT": "{PORT}", "SERVER_PORT": "{PORT}"},
                    readiness=ReadinessProbe(type="tcp"),
                )
            )

    return candidates


def plan_from_candidates(candidates: List[ServiceCandidate] | list[dict]) -> RunPlan:
    if not candidates:
        return RunPlan(
            runnable=False,
            reason="No deterministic service candidates detected; deferring to LLM planner.",
            reasoning="No deterministic service candidates detected; deferring to LLM planner.",
            services=[],
            entry_service=None,
            confidence=0.2,
        )

    # Normalize dict candidates if passed
    normalized_cands: List[ServiceCandidate] = []
    for c in candidates:
        if isinstance(c, ServiceCandidate):
            normalized_cands.append(c)
        elif isinstance(c, dict):
            normalized_cands.append(
                ServiceCandidate(
                    name=c.get("name", "service"),
                    role=c.get("role", "backend"),
                    cwd=c.get("cwd", "."),
                    framework=c.get("framework", "generic"),
                    score=float(c.get("score", 0.8)),
                    runnable=bool(c.get("runnable", True)),
                    install=c.get("install", []),
                    build=c.get("build", []),
                    start=c.get("start", []),
                    env=c.get("env", {}),
                    readiness=ReadinessProbe(**c["readiness"]) if isinstance(c.get("readiness"), dict) else c.get("readiness"),
                )
            )

    runnable_cands = [c for c in normalized_cands if c.runnable]
    if not runnable_cands:
        # Pure mobile or library repository
        services = [
            ServiceSpec(
                name=c.name,
                role=c.role,
                cwd=c.cwd,
                install=[],
                build=[],
                start=[],
                env={},
                depends_on=[],
                readiness=None,
            )
            for c in normalized_cands
        ]
        return RunPlan(
            runnable=False,
            reason="Repository contains only non-web mobile or library targets.",
            reasoning="Repository contains only non-web mobile or library targets.",
            services=services,
            entry_service=None,
            confidence=0.90,
        )

    services: List[ServiceSpec] = []
    backend_names = [c.name for c in runnable_cands if c.role == "backend"]

    for c in normalized_cands:
        deps: List[str] = []
        env = dict(c.env)
        if c.role == "frontend" and backend_names:
            primary_backend = backend_names[0]
            deps.append(primary_backend)
            env.setdefault("VITE_API_URL", f"{{services.{primary_backend}.url}}")
            env.setdefault("REACT_APP_API_URL", f"{{services.{primary_backend}.url}}")
            env.setdefault("NEXT_PUBLIC_API_URL", f"{{services.{primary_backend}.url}}")

        services.append(
            ServiceSpec(
                name=c.name,
                role=c.role,
                cwd=c.cwd,
                install=c.install if c.runnable else [],
                build=c.build if c.runnable else [],
                start=c.start if c.runnable else [],
                env=env,
                depends_on=deps,
                readiness=c.readiness if c.runnable else None,
            )
        )

    # Prefer frontend as entry_service if a runnable web SPA exists alongside backend, otherwise primary backend
    frontend_cands = [c for c in runnable_cands if c.role in ("frontend", "fullstack")]
    entry_svc = frontend_cands[0].name if frontend_cands else runnable_cands[0].name
    max_score = max(c.score for c in runnable_cands)

    framework_list = ", ".join(c.framework for c in normalized_cands)
    return RunPlan(
        runnable=True,
        services=services,
        entry_service=entry_svc,
        confidence=round(max_score, 2),
        reason=f"Deterministic plan constructed for {framework_list}.",
        reasoning=f"Deterministic plan constructed for {framework_list}.",
    )
