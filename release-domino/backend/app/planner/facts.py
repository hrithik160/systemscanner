from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    "target",
    ".rd_cache",
    ".cache",
    "coverage",
}

ROUTE_DECORATOR_RE = re.compile(
    r"""(?:@(?:app|router|bp|api)\.(?:get|post|put|delete|patch|route)|"""
    r"""(?:app|router)\.(?:get|post|put|delete|use)|"""
    r"""@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)|"""
    r"""\.(?:GET|POST|PUT|DELETE|HandleFunc))\s*\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


@dataclass
class RepoFacts:
    root: str
    files: List[str] = field(default_factory=list)
    manifests: Dict[str, str] = field(default_factory=dict)
    py_imports: Dict[str, List[str]] = field(default_factory=dict)
    js_deps: Dict[str, Dict[str, str]] = field(default_factory=dict)
    has_index_html: Dict[str, bool] = field(default_factory=dict)
    procfile: Dict[str, str] = field(default_factory=dict)
    dockerfile_cmds: List[str] = field(default_factory=list)
    compose_services: List[str] = field(default_factory=list)
    readme_commands: List[str] = field(default_factory=list)
    route_map: Dict[str, str] = field(default_factory=dict)  # URL path prefix -> relative file path

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tree"] = self.files
        d["code_imports"] = [imp for imps in self.py_imports.values() for imp in imps]
        return d

    def get(self, key: str, default: Any = None) -> Any:
        if key == "tree":
            return self.files
        if key == "code_imports":
            return [imp for imps in self.py_imports.values() for imp in imps]
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if key == "tree":
            return self.files
        if key == "code_imports":
            return [imp for imps in self.py_imports.values() for imp in imps]
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key in ("tree", "code_imports")


def _extract_py_imports_and_routes(py_file: Path, rel_path: str, route_map: Dict[str, str]) -> List[str]:
    imports: Set[str] = set()
    try:
        source = py_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    # Extract HTTP routes via regex for fast cross-framework coverage
    for match in ROUTE_DECORATOR_RE.finditer(source):
        route_path = match.group(1).strip()
        if route_path.startswith("/"):
            route_map.setdefault(route_path, rel_path)

    # Extract top-level Python imports via AST
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    except SyntaxError:
        # Fallback regex if file has Python 2 or partial syntax
        for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z0-9_]+)", source, re.MULTILINE):
            imports.add(m.group(1))

    return sorted(imports)


def _extract_routes_generic(file_path: Path, rel_path: str, route_map: Dict[str, str]) -> None:
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in ROUTE_DECORATOR_RE.finditer(source):
            route_path = match.group(1).strip()
            if route_path.startswith("/"):
                route_map.setdefault(route_path, rel_path)
    except Exception:
        pass


def gather_repo_facts(repo_path: Path | str, max_files: int = 400, max_depth: int = 4) -> RepoFacts:
    repo_path = Path(repo_path).resolve()
    facts = RepoFacts(root=str(repo_path))

    manifest_names = {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "Procfile",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }

    for p in sorted(repo_path.rglob("*")):
        try:
            rel_parts = p.relative_to(repo_path).parts
        except ValueError:
            continue

        if any(part in IGNORE_DIRS or (part.startswith(".") and part != ".env.example") for part in rel_parts):
            continue
        if len(rel_parts) > max_depth:
            continue

        if p.is_file():
            rel_str = "/".join(rel_parts)
            if len(facts.files) < max_files:
                facts.files.append(rel_str)

            # 1. Manifests
            if p.name in manifest_names:
                try:
                    raw = p.read_text(encoding="utf-8", errors="ignore")
                    facts.manifests[rel_str] = "\n".join(raw.splitlines()[:60])
                except Exception:
                    pass

            # 2. package.json parsing & Web SPA vs Mobile disambiguation
            if p.name == "package.json":
                pkg_dir = p.parent
                rel_dir = "." if pkg_dir == repo_path else pkg_dir.relative_to(repo_path).as_posix()
                try:
                    data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                    deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {}),
                    }
                    facts.js_deps[rel_dir] = deps
                    has_html = any(
                        (pkg_dir / candidate).exists()
                        for candidate in ("index.html", "public/index.html", "src/index.html", "app/page.tsx", "pages/index.tsx", "pages/index.js")
                    )
                    facts.has_index_html[rel_dir] = has_html
                except Exception:
                    pass

            # 3. Procfile
            if p.name == "Procfile":
                try:
                    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if ":" in line and not line.strip().startswith("#"):
                            k, v = line.split(":", 1)
                            facts.procfile[k.strip()] = v.strip()
                except Exception:
                    pass

            # 4. Dockerfile CMD / ENTRYPOINT
            if p.name == "Dockerfile":
                try:
                    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                        s = line.strip()
                        if s.upper().startswith(("CMD ", "ENTRYPOINT ", "EXPOSE ")):
                            facts.dockerfile_cmds.append(s)
                except Exception:
                    pass

            # 5. README commands
            if p.name.lower() in ("readme.md", "readme.txt"):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    for m in re.finditer(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", text, re.DOTALL | re.IGNORECASE):
                        for cmd_line in m.group(1).splitlines():
                            c = cmd_line.strip().lstrip("$> ").strip()
                            if c and not c.startswith("#") and len(facts.readme_commands) < 20:
                                facts.readme_commands.append(c)
                except Exception:
                    pass

            # 6. Python AST imports & route mapping
            if p.suffix == ".py":
                py_imps = _extract_py_imports_and_routes(p, rel_str, facts.route_map)
                if py_imps:
                    facts.py_imports[rel_str] = py_imps

            # 7. JS/TS/Go/Rust/Java route mapping for [ACTIVE_NODE]
            elif p.suffix in (".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"):
                _extract_routes_generic(p, rel_str, facts.route_map)

    return facts


def compute_repo_fingerprint(facts: RepoFacts | dict) -> str:
    """Computes a stable SHA-256 fingerprint over repository structure and manifests."""
    hasher = hashlib.sha256()
    files = facts.get("files", []) if isinstance(facts, (dict, RepoFacts)) else []
    manifests = facts.get("manifests", {}) if isinstance(facts, (dict, RepoFacts)) else {}
    hasher.update(json.dumps(sorted(files)).encode("utf-8"))
    for k in sorted(manifests.keys()):
        hasher.update(k.encode("utf-8"))
        hasher.update(manifests[k].encode("utf-8"))
    return hasher.hexdigest()[:16]
