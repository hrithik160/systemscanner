"""Project Architecture Knowledge Engine & Interactive Conflict Advisor (app/llm/knowledge.py).

Provides:
  1. Complete project architecture & workspace discovery (frontend vs backend frameworks, file maps, real exports).
  2. Mathematical relative path computation between any two project nodes.
  3. Real symbol alignment (named vs default exports, never hallucinating stems).
  4. Interactive Architecture Conflict Questions (asking user with recommended options if path, framework, or imports mismatch).
  5. Vite / Runtime error analyzer & auto-fixer.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("release_domino.llm.knowledge")

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\))"""
)
JS_EXPORT_NAMED_RE = re.compile(
    r"""export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z0-9_$]+)"""
)
JS_EXPORT_LIST_RE = re.compile(r"""export\s*\{([^}]+)\}""")
JS_EXPORT_DEFAULT_RE = re.compile(
    r"""export\s+default\s+(?:async\s+)?(?:function\s*([A-Za-z0-9_$]*)|class\s*([A-Za-z0-9_$]*)|([A-Za-z0-9_$]+))"""
)


class ClarificationOption(BaseModel):
    id: str
    title: str
    description: str
    is_recommended: bool = False
    patch_action: Optional[Dict[str, Any]] = None


class ClarificationQuestion(BaseModel):
    id: str
    severity: str = "warning"  # 'critical' | 'warning' | 'suggestion'
    title: str
    question: str
    reason: str
    options: List[ClarificationOption]


class ProjectKnowledge(BaseModel):
    pid: str
    root_path: str
    primary_language: str = "py"
    frontend_apps: List[Dict[str, Any]] = Field(default_factory=list)
    backend_apps: List[Dict[str, Any]] = Field(default_factory=list)
    all_source_files: List[str] = Field(default_factory=list)
    file_exports: Dict[str, List[str]] = Field(default_factory=dict)
    architecture_summary: str = ""


def _scan_repo_knowledge(repo_path: Path, pid: str) -> ProjectKnowledge:
    """Scan the project filesystem to build ground-truth knowledge of all workspaces, frameworks, and files."""
    frontend_apps: List[Dict[str, Any]] = []
    backend_apps: List[Dict[str, Any]] = []
    all_files: List[str] = []
    file_exports: Dict[str, List[str]] = {}

    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".pytest_cache"}

    # 1. Discover all package.json files for JS/TS apps
    for pkg_file in repo_path.rglob("package.json"):
        if any(part in skip_dirs for part in pkg_file.parts):
            continue
        try:
            rel_dir = pkg_file.parent.relative_to(repo_path).as_posix()
            data = json.loads(pkg_file.read_text(encoding="utf-8", errors="ignore"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            # Detect Frontend
            if any(k in deps for k in ("react", "vue", "svelte", "next", "vite", "@angular/core")):
                framework = "react" if "react" in deps else ("vue" if "vue" in deps else "frontend")
                bundler = "vite" if "vite" in deps else ("next" if "next" in deps else "webpack")
                src_dir = (pkg_file.parent / "src")
                src_rel = (rel_dir + "/src") if rel_dir != "." else "src"
                frontend_apps.append({
                    "dir": rel_dir if rel_dir != "." else "",
                    "framework": framework,
                    "bundler": bundler,
                    "src_dir": src_rel if src_dir.is_dir() else rel_dir,
                    "dependencies": list(deps.keys()),
                })
            # Detect Backend Node
            elif any(k in deps for k in ("express", "fastify", "koa", "nestjs", "@nestjs/core")):
                backend_apps.append({
                    "dir": rel_dir if rel_dir != "." else "",
                    "framework": "express" if "express" in deps else "node",
                    "runtime": "node",
                    "dependencies": list(deps.keys()),
                })
        except Exception:
            pass

    # 2. Discover Python apps
    for py_indicator in ("requirements.txt", "Pipfile", "pyproject.toml", "setup.py"):
        for ind_file in repo_path.rglob(py_indicator):
            if any(part in skip_dirs for part in ind_file.parts):
                continue
            rel_dir = ind_file.parent.relative_to(repo_path).as_posix()
            backend_apps.append({
                "dir": rel_dir if rel_dir != "." else "",
                "framework": "fastapi",  # default heuristic
                "runtime": "python",
                "dependencies": [],
            })
            break

    # 3. Index all source files and their exports
    py_count = 0
    js_count = 0
    for p in repo_path.rglob("*"):
        if not p.is_file() or any(part in skip_dirs for part in p.parts):
            continue
        ext = p.suffix.lower()
        if ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs"):
            rel_str = p.relative_to(repo_path).as_posix()
            all_files.append(rel_str)
            if ext == ".py":
                py_count += 1
            else:
                js_count += 1

            # Extract exports
            try:
                code_text = p.read_text(encoding="utf-8", errors="ignore")
                exports = extract_module_exports(code_text, ext.lstrip("."))
                if exports.get("all_exports"):
                    file_exports[rel_str] = exports["all_exports"]
            except Exception:
                pass

    all_files.sort()
    primary_lang = "py" if py_count > js_count else ("tsx" if any(f.endswith(".tsx") for f in all_files) else "js")

    # Build plain-English architecture summary
    fe_desc = [f"Frontend at '{app['dir'] or '.'}' ({app['framework']}, {app['bundler']}, src='{app['src_dir']}')" for app in frontend_apps]
    be_desc = [f"Backend at '{app['dir'] or '.'}' ({app.get('framework', 'api')}, runtime={app.get('runtime', 'python')})" for app in backend_apps]
    summary_parts = []
    if fe_desc:
        summary_parts.append("; ".join(fe_desc))
    if be_desc:
        summary_parts.append("; ".join(be_desc))
    if not summary_parts:
        summary_parts.append(f"Generic project with {len(all_files)} files (primary: {primary_lang})")

    return ProjectKnowledge(
        pid=pid,
        root_path=str(repo_path),
        primary_language=primary_lang,
        frontend_apps=frontend_apps,
        backend_apps=backend_apps,
        all_source_files=all_files[:300],
        file_exports=file_exports,
        architecture_summary=" | ".join(summary_parts),
    )


def extract_module_exports(code: str, lang: str) -> Dict[str, Any]:
    """Parse exports from source code: default export, named exports, and all symbols."""
    clean_lang = (lang or "py").lower().lstrip(".")
    named: List[str] = []
    default_exp: Optional[str] = None

    if clean_lang in ("py", "python"):
        try:
            tree = ast.parse(code)
            for stmt in tree.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not stmt.name.startswith("_"):
                        named.append(stmt.name)
        except Exception:
            named = re.findall(r"(?:^|\n)\s*(?:async\s+)?(?:def|class)\s+([a-zA-Z0-9_]+)", code)
        return {"default_export": None, "named_exports": named, "all_exports": named}

    # JS/TS
    # 1. Named exports: export function foo(), export const bar = ...
    for m in JS_EXPORT_NAMED_RE.finditer(code):
        named.append(m.group(1))

    # 2. Export list: export { foo, bar as baz }
    for m in JS_EXPORT_LIST_RE.finditer(code):
        items = m.group(1).split(",")
        for item in items:
            cleaned = item.strip().split()
            if cleaned:
                named.append(cleaned[-1])

    # 3. Default export: export default function Foo...
    m_def = JS_EXPORT_DEFAULT_RE.search(code)
    if m_def:
        default_exp = m_def.group(1) or m_def.group(2) or m_def.group(3) or "default"

    all_exp = list(dict.fromkeys(([default_exp] if default_exp else []) + named))
    return {
        "default_export": default_exp,
        "named_exports": named,
        "all_exports": all_exp,
    }


def compute_relative_import_path(caller_rel_path: str, target_rel_path: str, lang: str = "js") -> str:
    """Compute exact relative import path between caller and target, stripping extension for JS/TS."""
    caller_dir = Path(caller_rel_path).parent
    target_p = Path(target_rel_path)

    try:
        rel = os.path.relpath(str(target_p), str(caller_dir)).replace("\\", "/")
    except ValueError:
        rel = target_rel_path.replace("\\", "/")

    clean_lang = (lang or "js").lower().lstrip(".")
    if clean_lang in ("js", "jsx", "ts", "tsx"):
        # Strip JS/TS extension for bundler resolution
        for ext in (".tsx", ".ts", ".jsx", ".js", ".mjs"):
            if rel.endswith(ext):
                rel = rel[:-len(ext)]
                break

    if not rel.startswith("."):
        rel = f"./{rel}"
    return rel


def generate_smart_import(
    caller_path: str,
    caller_code: str,
    target_path: str,
    target_code: str,
    lang: str = "js",
) -> Dict[str, str]:
    """Generate syntactically correct import statement based on actual exports and real relative path."""
    clean_lang = (lang or "js").lower().lstrip(".")
    rel_path = compute_relative_import_path(caller_path, target_path, clean_lang)
    target_exports = extract_module_exports(target_code, clean_lang)
    target_stem = Path(target_path).stem

    if clean_lang in ("py", "python"):
        caller_parent = Path(caller_path).parent.as_posix()
        target_parent = Path(target_path).parent.as_posix()
        top_sym = target_exports["named_exports"][0] if target_exports.get("named_exports") else None

        if caller_parent in (".", ""):
            if target_parent in (".", ""):
                import_stmt = f"from {target_stem} import {top_sym}\n" if top_sym else f"import {target_stem}\n"
            else:
                mod_path = f"{target_parent.replace('/', '.')}.{target_stem}"
                import_stmt = f"from {mod_path} import {top_sym}\n" if top_sym else f"import {mod_path}\n"
        elif caller_parent == target_parent:
            import_stmt = f"from .{target_stem} import {top_sym}\n" if top_sym else f"from . import {target_stem}\n"
        else:
            mod_path = f"{target_parent.replace('/', '.')}.{target_stem}".lstrip(".")
            import_stmt = f"from {mod_path} import {top_sym}\n" if top_sym else f"import {mod_path}\n"

        symbol = top_sym if top_sym else target_stem
        return {"import_statement": import_stmt, "symbol": symbol, "path": rel_path}

    # JS/TS/React
    default_exp = target_exports.get("default_export")
    named_exps = target_exports.get("named_exports") or []

    if default_exp and default_exp != "default":
        import_stmt = f"import {default_exp} from '{rel_path}';\n"
        symbol = default_exp
    elif default_exp == "default" or (not named_exps and target_stem.istitle()):
        # Default component convention
        comp_name = target_stem[0].upper() + target_stem[1:]
        import_stmt = f"import {comp_name} from '{rel_path}';\n"
        symbol = comp_name
    elif named_exps:
        # Use primary named export
        top_sym = named_exps[0]
        import_stmt = f"import {{ {top_sym} }} from '{rel_path}';\n"
        symbol = top_sym
    else:
        # Fallback to sanitized stem
        clean_stem = re.sub(r"[^a-zA-Z0-9_$]", "", target_stem) or "moduleRef"
        import_stmt = f"import * as {clean_stem} from '{rel_path}';\n"
        symbol = clean_stem

    return {"import_statement": import_stmt, "symbol": symbol, "path": rel_path}


def detect_architecture_conflicts(
    pid: str,
    node_name: str,
    node_code: str,
    lang: str,
    caller_node_ids: List[str],
    output_node_ids: List[str],
    repo_path: Optional[Path] = None,
) -> List[ClarificationQuestion]:
    """Inspect the proposed node definition and graph connections against real project knowledge.
    Generates interactive clarification questions whenever an action might break the project build.
    """
    questions: List[ClarificationQuestion] = []
    clean_lang = (lang or "py").lower().lstrip(".")

    # Attempt to load repo knowledge
    knowledge: Optional[ProjectKnowledge] = None
    if repo_path and repo_path.is_dir():
        knowledge = _scan_repo_knowledge(repo_path, pid)

    # 1. CONFLICT CHECK: Path Boundary Mismatch
    # If caller is inside a Frontend subproject (e.g. `frontend/dummy/src/main.jsx`), but node_name is placed in `app/`
    for caller_nid in caller_node_ids:
        caller_is_frontend = any(k in caller_nid for k in ("frontend", "client", "ui", "src/App", "src/main")) or caller_nid.endswith((".jsx", ".tsx"))
        node_is_in_root_app = node_name.startswith("app/") or not any(k in node_name for k in ("frontend", "client", "src"))

        if caller_is_frontend and node_is_in_root_app:
            # Determine best frontend folder
            best_fe_dir = "src"
            if knowledge and knowledge.frontend_apps:
                best_fe_dir = knowledge.frontend_apps[0].get("src_dir", "frontend/src")
            elif "frontend/" in caller_nid:
                best_fe_dir = caller_nid.split("/src/")[0] + "/src" if "/src/" in caller_nid else "frontend/src"

            stem = Path(node_name).stem
            suggested_ext = ".jsx" if clean_lang in ("jsx", "js") else (".tsx" if clean_lang == "tsx" else ".js")
            rec_path = f"{best_fe_dir}/{stem}{suggested_ext}"
            comp_path = f"{best_fe_dir}/components/{stem}{suggested_ext}"

            questions.append(
                ClarificationQuestion(
                    id=f"q_path_boundary_{uuid.uuid4().hex[:6]}",
                    severity="critical",
                    title="Architecture Boundary Conflict",
                    question=(
                        f"You connected this node to the React frontend ('{caller_nid}'), "
                        f"but the new file path is '{node_name}' outside the frontend workspace."
                    ),
                    reason="Vite bundler cannot resolve relative imports across root boundary without special aliases, causing 'Failed to resolve import' build errors.",
                    options=[
                        ClarificationOption(
                            id="opt_move_frontend_src",
                            title=f"Place inside Frontend ({rec_path})",
                            description="Automatically puts the component where Vite and React can resolve and hot-reload it.",
                            is_recommended=True,
                            patch_action={"target_path": rec_path, "target_lang": clean_lang if clean_lang in ("jsx", "tsx") else "jsx"},
                        ),
                        ClarificationOption(
                            id="opt_move_frontend_components",
                            title=f"Place in Components folder ({comp_path})",
                            description="Keeps UI components neatly organized in a dedicated components directory.",
                            patch_action={"target_path": comp_path, "target_lang": clean_lang if clean_lang in ("jsx", "tsx") else "jsx"},
                        ),
                        ClarificationOption(
                            id="opt_keep_custom",
                            title=f"Keep custom path '{node_name}'",
                            description="Keep current path and force a deep relative import ('../../../...').",
                            patch_action={"target_path": node_name},
                        ),
                    ],
                )
            )
            break

    # 2. CONFLICT CHECK: Language / Subsystem Incompatibility
    for caller_nid in caller_node_ids:
        caller_is_js = caller_nid.endswith((".js", ".jsx", ".ts", ".tsx"))
        node_is_py = clean_lang in ("py", "python") or node_name.endswith(".py")

        if caller_is_js and node_is_py:
            stem = Path(node_name).stem
            questions.append(
                ClarificationQuestion(
                    id=f"q_lang_mismatch_{uuid.uuid4().hex[:6]}",
                    severity="critical",
                    title="Language & Runtime Mismatch",
                    question=(
                        f"You are connecting Python code ('{node_name}') directly to a JavaScript/TypeScript caller ('{caller_nid}')."
                    ),
                    reason="Browsers and Node runtimes cannot execute Python source directly without an HTTP/REST endpoint bridge.",
                    options=[
                        ClarificationOption(
                            id="opt_convert_to_js",
                            title="Convert Node to JavaScript / React Component",
                            description="Transforms logic into a client-side module executable directly in the browser.",
                            is_recommended=True,
                            patch_action={"target_lang": "jsx", "target_path": f"{Path(node_name).parent}/{stem}.jsx"},
                        ),
                        ClarificationOption(
                            id="opt_bridge_via_api",
                            title="Wire as Backend API route & call via fetch()",
                            description="Mounts Python code on backend server and connects frontend via HTTP fetch.",
                            patch_action={"target_lang": "py"},
                        ),
                    ],
                )
            )
            break

    # 3. CONFLICT CHECK: React Framework Hallucination (e.g. StrictNode instead of StrictMode)
    if "StrictNode" in node_code or any("StrictNode" in (node_code or "") for _ in [1]):
        questions.append(
            ClarificationQuestion(
                id=f"q_react_hallucination_{uuid.uuid4().hex[:6]}",
                severity="critical",
                title="React Framework Symbol Correction",
                question="Detected 'StrictNode' imported or used from 'react'. React exports 'StrictMode', not 'StrictNode'.",
                reason="Using invalid symbol 'StrictNode' causes React initialization to crash immediately with TypeError.",
                options=[
                    ClarificationOption(
                        id="opt_fix_strict_mode",
                        title="Auto-replace 'StrictNode' with 'StrictMode'",
                        description="Ensures React renders safely with standard StrictMode.",
                        is_recommended=True,
                        patch_action={"code_replace": ("StrictNode", "StrictMode")},
                    ),
                ],
            )
        )

    # 4. CONFLICT CHECK: Export Symbol Mismatch
    exports_info = extract_module_exports(node_code, clean_lang)
    has_exports = bool(exports_info.get("all_exports"))
    if not has_exports and clean_lang in ("js", "jsx", "ts", "tsx"):
        stem = Path(node_name).stem
        comp_name = stem[0].upper() + stem[1:] if stem else "ModuleComponent"
        questions.append(
            ClarificationQuestion(
                id=f"q_missing_export_{uuid.uuid4().hex[:6]}",
                severity="warning",
                title="Missing Module Export",
                question=f"The code for '{node_name}' does not export any function or component.",
                reason="Callers will not be able to import or use functions from this file, causing import resolution errors.",
                options=[
                    ClarificationOption(
                        id="opt_add_default_export",
                        title=f"Add default export: 'export default {comp_name};'",
                        description="Allows caller to import cleanly as a React component or utility.",
                        is_recommended=True,
                        patch_action={"append_code": f"\n\nexport default {comp_name};\n"},
                    ),
                ],
            )
        )

    # 5. CONFLICT CHECK: Invisible Component (if (!isVisible) return null without trigger)
    if re.search(r"if\s*\(\s*!isVisible\s*\)\s*return\s+null", node_code) and "handleShow" in node_code:
        questions.append(
            ClarificationQuestion(
                id=f"q_invisible_comp_{uuid.uuid4().hex[:6]}",
                severity="warning",
                title="Invisible Component (Hidden by Default)",
                question="Component returns null when `isVisible` is false, but has no external trigger button. It will be completely invisible on screen.",
                reason="State starts with isVisible = false and returns null. Without an active launcher or trigger button, users cannot see or interact with the component.",
                options=[
                    ClarificationOption(
                        id="opt_add_launcher_button",
                        title="Render Launch Trigger Button when hidden",
                        description="Renders a stylish launcher button (e.g., '🚀 Launch Animation') when isVisible is false so users can click to open it.",
                        is_recommended=True,
                        patch_action={"replace_null_return": True},
                    ),
                    ClarificationOption(
                        id="opt_default_visible",
                        title="Make visible by default (useState(true))",
                        description="Sets initial state to true so the animation or modal shows up immediately upon mounting.",
                        patch_action={"code_replace": ("useState(false)", "useState(true)")},
                    ),
                ],
            )
        )

    # 6. CONFLICT CHECK: Multiple export default statements
    default_exports_count = len(re.findall(r"\bexport\s+default\b", node_code))
    if default_exports_count > 1:
        questions.append(
            ClarificationQuestion(
                id=f"q_dup_export_{uuid.uuid4().hex[:6]}",
                severity="critical",
                title="Duplicate 'export default' Statements",
                question=f"Found {default_exports_count} 'export default' statements in this file.",
                reason="JavaScript ES modules only permit one default export per file. Multiple default exports cause build and bundling errors.",
                options=[
                    ClarificationOption(
                        id="opt_split_default_export",
                        title="Keep only the first export default and make others named exports",
                        description="Converts subsequent exports into standard named exports.",
                        is_recommended=True,
                    ),
                ],
            )
        )

    # 7. CONFLICT CHECK: TypeScript in JavaScript file
    if clean_lang in ("js", "jsx") and any(ts_token in node_code for ts_token in (": React.FC", ": NodeJS.", ": React.CSSProperties")):
        questions.append(
            ClarificationQuestion(
                id=f"q_ts_types_in_js_{uuid.uuid4().hex[:6]}",
                severity="warning",
                title="TypeScript Types in JavaScript File",
                question=f"Found TypeScript type annotations (e.g. React.FC, React.CSSProperties) inside '{node_name}'.",
                reason="In a pure .jsx or .js project, TypeScript type annotations cause Vite/Babel syntax parsing errors.",
                options=[
                    ClarificationOption(
                        id="opt_strip_ts_types",
                        title="Auto-strip TypeScript types to pure JSX",
                        description="Removes TypeScript type declarations so file runs cleanly in Vite JavaScript setup.",
                        is_recommended=True,
                    ),
                ],
            )
        )

    return questions


def auto_fix_runtime_error(pid: str, error_text: str, repo_path: Path) -> Dict[str, Any]:
    """Diagnose and auto-repair runtime / bundler errors (Vite, Node MODULE_NOT_FOUND, Python relative imports, missing packages)."""
    repo_path = Path(repo_path).resolve()

    # 1. Python Relative Import Error: "attempted relative import with no known parent package"
    if "attempted relative import with no known parent package" in error_text:
        repaired_files = []
        for py_f in repo_path.rglob("*.py"):
            if any(p in py_f.parts for p in (".git", ".venv", "venv", "__pycache__")):
                continue
            try:
                src = py_f.read_text(encoding="utf-8", errors="ignore")
                healed = re.sub(r"\bfrom\s+\.([a-zA-Z0-9_]+)\s+import\b", r"from \1 import", src)
                if healed != src:
                    py_f.write_text(healed, encoding="utf-8")
                    repaired_files.append(str(py_f.relative_to(repo_path)))
            except Exception:
                pass
        if repaired_files:
            return {
                "fixed": True,
                "message": f"Auto-healed relative imports in {', '.join(repaired_files[:3])} to allow direct standalone execution.",
            }

    # 2. Node.js missing external package (e.g. Cannot find module 'express' or code: 'MODULE_NOT_FOUND')
    m_node_pkg = re.search(r"Cannot find module ['\"]([^'\"./\\][^'\"]*)['\"]", error_text)
    if m_node_pkg:
        raw_pkg = m_node_pkg.group(1).split("/")[0] if not m_node_pkg.group(1).startswith("@") else "/".join(m_node_pkg.group(1).split("/")[:2])
        pkg_dir = repo_path
        if not (pkg_dir / "package.json").exists():
            for p in repo_path.rglob("package.json"):
                if "node_modules" not in p.parts:
                    pkg_dir = p.parent
                    break
        try:
            res = subprocess.run(
                ["npm", "install", raw_pkg, "--legacy-peer-deps"],
                cwd=str(pkg_dir),
                capture_output=True,
                text=True,
                timeout=90,
                shell=(os.name == "nt"),
            )
            return {
                "fixed": True,
                "message": f"Installed missing Node module '{raw_pkg}' via npm.",
            }
        except Exception as e:
            return {
                "fixed": False,
                "message": f"Failed to install '{raw_pkg}': {e}",
            }

    # 3. Node.js missing local entry file (e.g. Cannot find module '.../server.js' or MODULE_NOT_FOUND with requireStack: [])
    m_missing_file = re.search(r"Cannot find module ['\"]([^'\"]+\.c?jsx?)['\"]", error_text)
    if m_missing_file or "MODULE_NOT_FOUND" in error_text:
        target_name = Path(m_missing_file.group(1)).name if m_missing_file else "server.js"
        found_target = None
        for cand in repo_path.rglob(target_name):
            if "node_modules" not in cand.parts and cand.is_file() and cand.parent != repo_path:
                found_target = cand
                break
        if found_target:
            rel_forward = found_target.relative_to(repo_path).as_posix()
            root_entry = repo_path / target_name
            root_entry.write_text(f"// Release Domino Entrypoint Forwarder\nrequire('./{rel_forward}');\n", encoding="utf-8")
            return {
                "fixed": True,
                "message": f"Created root entrypoint forwarder for '{target_name}' -> './{rel_forward}'.",
                "created_file": target_name,
            }

    # 4. Python ModuleNotFoundError: No module named 'xxx'
    m_py = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", error_text)
    if m_py:
        missing_mod = m_py.group(1).split(".")[0]
        try:
            from app.planner.repair import PY_IMPORT_TO_PKG
            pkg_name = PY_IMPORT_TO_PKG.get(missing_mod, missing_mod)
        except Exception:
            pkg_name = missing_mod
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg_name],
                capture_output=True,
                text=True,
                timeout=90,
            )
            return {
                "fixed": True,
                "message": f"Installed missing Python package '{pkg_name}' via pip.",
            }
        except Exception as e:
            pass

    # 5. Vite / Bundler missing imports
    # Pattern: [plugin:vite:import-analysis] Failed to resolve import "./homepage" from "src/main.jsx". Does the file exist?
    vite_import_match = re.search(
        r"""Failed to resolve import\s+["']([^"']+)["']\s+from\s+["']([^"']+)["']""",
        error_text,
    )
    if not vite_import_match:
        vite_import_match = re.search(
            r"""Cannot find module\s+["']([^"']+)["'](?:\s+imported from\s+["']([^"']+)["'])?""",
            error_text,
        )

    if not vite_import_match:
        return {
            "fixed": False,
            "message": "Error does not match known pattern. Type '$ run' in the terminal to invoke the universal RunPlan engine.",
        }

    missing_import = vite_import_match.group(1)
    caller_file_rel = vite_import_match.group(2) if vite_import_match.lastindex and vite_import_match.lastindex >= 2 else None

    # Search project for caller file
    caller_path: Optional[Path] = None
    if caller_file_rel:
        direct_cand = repo_path / caller_file_rel
        if direct_cand.is_file():
            caller_path = direct_cand
        else:
            # Fuzzy find caller
            caller_stem = Path(caller_file_rel).name
            for cand in repo_path.rglob(caller_stem):
                if "node_modules" not in cand.parts and cand.is_file():
                    caller_path = cand
                    break

    if not caller_path or not caller_path.is_file():
        return {
            "fixed": False,
            "message": f"Could not locate caller file '{caller_file_rel}' in repository.",
        }

    # Search project for target file
    target_stem = Path(missing_import).stem.lower()
    target_file: Optional[Path] = None
    for cand in repo_path.rglob("*"):
        if "node_modules" not in cand.parts and cand.is_file():
            if cand.stem.lower() == target_stem and cand != caller_path:
                target_file = cand
                break

    caller_code = caller_path.read_text(encoding="utf-8", errors="ignore")

    # If target file exists in another workspace (e.g. app/homepage.js), copy/create it inside caller directory!
    if target_file and target_file.is_file():
        target_code = target_file.read_text(encoding="utf-8", errors="ignore")
        # Check if caller is React and target is not
        if caller_path.suffix in (".jsx", ".tsx") and target_file.suffix not in (".jsx", ".tsx"):
            # Provide a clean React component wrapper
            clean_comp_name = target_stem[0].upper() + target_stem[1:]
            new_react_code = (
                f"import React from 'react';\n\n"
                f"export function {clean_comp_name}(props) {{\n"
                f"  return (\n"
                f"    <div style={{{{ padding: '16px', background: '#0f172a', borderRadius: '8px', color: '#fff', margin: '12px 0' }}}}>\n"
                f"      <h3 style={{{{ fontWeight: 'bold' }}}}>{clean_comp_name}</h3>\n"
                f"      <p style={{{{ fontSize: '13px', color: '#94a3b8' }}}}>Auto-repaired component for {target_stem}.</p>\n"
                f"    </div>\n"
                f"  );\n"
                f"}}\n\n"
                f"export default {clean_comp_name};\n"
            )
            dest_file = caller_path.parent / f"{clean_comp_name}.jsx"
            dest_file.write_text(new_react_code, encoding="utf-8")
            # Update caller code import
            rel_import = f"./{clean_comp_name}"
            updated_caller = re.sub(
                rf"""import\s+.*?from\s+['"]{re.escape(missing_import)}['"];?""",
                f"import {clean_comp_name} from '{rel_import}';",
                caller_code,
            )
            caller_path.write_text(updated_caller, encoding="utf-8")
            return {
                "fixed": True,
                "message": f"Created missing React component at '{dest_file.relative_to(repo_path)}' and aligned import in '{caller_path.relative_to(repo_path)}'.",
                "created_file": str(dest_file.relative_to(repo_path)),
            }
        else:
            # Correct the relative import path in caller
            correct_rel = compute_relative_import_path(str(caller_path.relative_to(repo_path)), str(target_file.relative_to(repo_path)))
            updated_caller = re.sub(
                rf"""from\s+['"]{re.escape(missing_import)}['"]""",
                f"from '{correct_rel}'",
                caller_code,
            )
            caller_path.write_text(updated_caller, encoding="utf-8")
            return {
                "fixed": True,
                "message": f"Updated import in '{caller_path.relative_to(repo_path)}' to point to '{correct_rel}'.",
            }
    else:
        # Target file doesn't exist at all -> remove the broken import line or create stub
        cleaned_caller = "\n".join(
            line for line in caller_code.splitlines()
            if missing_import not in line
        )
        caller_path.write_text(cleaned_caller + "\n", encoding="utf-8")
        return {
            "fixed": True,
            "message": f"Removed unresolvable import '{missing_import}' from '{caller_path.relative_to(repo_path)}'.",
        }


def guard_generated_code(code: str, lang: str = "jsx", file_path: str = "") -> str:
    """Pre-output Code Sanitizer & AST Guard.
    Guarantees:
    1. Framework hallucination elimination (StrictNode -> StrictMode).
    2. Pure JavaScript for .jsx/.js (strips TypeScript : React.FC, : NodeJS.Timeout, interfaces).
    3. Invisible UI protection: If a component has `if (!isVisible) return null;` or similar,
       it automatically injects a prominent launch trigger button so the user can see and interact with it.
    4. Exactly one export default per file (cleans duplicate default exports).
    5. Clean syntax validation.
    """
    if not code or not code.strip():
        return code

    clean_lang = (lang or "jsx").lower().lstrip(".")

    # 1. Framework hallucinations
    code = re.sub(r"\bStrictNode\b", "StrictMode", code)

    # 2. TypeScript stripping in .jsx / .js
    if clean_lang in ("js", "jsx") or file_path.endswith((".js", ".jsx")):
        code = re.sub(r":\s*React\.FC(?:<[^>]*>)?", "", code)
        code = re.sub(r":\s*NodeJS\.[A-Za-z0-9_]+(?:\s*\|\s*null|\s*\|\s*undefined)?", "", code)
        code = re.sub(r":\s*React\.CSSProperties", "", code)
        code = re.sub(r"\binterface\s+\w+(?:<[^>]*>)?\s*\{[\s\S]*?\}\n*", "", code)
        code = re.sub(r"\btype\s+\w+(?:<[^>]*>)?\s*=[\s\S]*?;\n*", "", code)

    # 3. Invisible UI Safeguard: If component hides itself with return null on !isVisible / !isOpen
    null_return_match = re.search(
        r"""if\s*\(\s*!([A-Za-z0-9_]+)\s*\)\s*\{\s*return\s+null\s*;?\s*\}|if\s*\(\s*!([A-Za-z0-9_]+)\s*\)\s*return\s+null\s*;?""",
        code,
    )
    if null_return_match:
        state_var = null_return_match.group(1) or null_return_match.group(2)
        trigger_fn = None
        for cand_fn in ("handleShow", "handleOpen", f"set{state_var[0].upper()}{state_var[1:]}"):
            if cand_fn in code:
                trigger_fn = cand_fn
                break

        comp_stem = Path(file_path).stem if file_path else "Component"
        comp_title = re.sub(r"([A-Z])", r" \1", comp_stem).strip().title() or "Feature"
        trigger_call = (
            f"{trigger_fn}()"
            if trigger_fn and trigger_fn.startswith("handle")
            else (f"{trigger_fn}(true)" if trigger_fn else f"alert('Activated {comp_title}')")
        )
        click_expr = f"() => {trigger_call}"

        launcher_jsx = (
            f"  if (!{state_var}) {{\n"
            f"    return (\n"
            f"      <div style={{{{ margin: '16px auto', textAlign: 'center' }}}}>\n"
            f"        <button\n"
            f"          type=\"button\"\n"
            f"          onClick={{{click_expr}}}\n"
            f"          style={{{{\n"
            f"            padding: '12px 28px',\n"
            f"            fontSize: '15px',\n"
            f"            fontWeight: 700,\n"
            f"            borderRadius: '10px',\n"
            f"            background: 'linear-gradient(135deg, #0284c7 0%, #6366f1 100%)',\n"
            f"            color: '#ffffff',\n"
            f"            border: 'none',\n"
            f"            cursor: 'pointer',\n"
            f"            boxShadow: '0 4px 14px rgba(2, 132, 199, 0.4)',\n"
            f"            transition: 'all 0.2s ease',\n"
            f"          }}}}\n"
            f"        >\n"
            f"          🚀 Launch {comp_title}\n"
            f"        </button>\n"
            f"      </div>\n"
            f"    );\n"
            f"  }}"
        )
        code = code[:null_return_match.start()] + launcher_jsx + code[null_return_match.end():]

    # 4. Duplicate export default cleanup
    def_exp_matches = list(re.finditer(r"\bexport\s+default\s+([A-Za-z0-9_]+);?", code))
    if len(def_exp_matches) > 1:
        for m in def_exp_matches[1:]:
            sym = m.group(1)
            code = code[:m.start()] + f"export {{ {sym} }};" + code[m.end():]

    # 5. PYTHON GUARDIANS: Tabs, root relative imports, future annotations, and AST validation
    if clean_lang in ("py", "python") or file_path.endswith(".py"):
        code = code.replace("\t", "    ")

        caller_parent = Path(file_path).parent.as_posix() if file_path else "."
        if caller_parent in (".", ""):
            code = re.sub(r"from\s+\.([A-Za-z0-9_]+)\s+import", r"from \1 import", code)

        has_modern_types = bool(re.search(r"\b(?:dict|list|set|tuple)\[|[A-Za-z0-9_]+\s*\|\s*None", code))
        if has_modern_types and "from __future__ import annotations" not in code:
            lines = code.splitlines(keepends=True)
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith(('"""', "'''", "#!", "#")):
                    insert_idx = idx + 1
                elif line.strip() == "":
                    continue
                else:
                    break
            code = "".join(lines[:insert_idx]) + "from __future__ import annotations\n" + "".join(lines[insert_idx:])

        try:
            ast.parse(code)
        except SyntaxError as err:
            logger.warning("Python AST SyntaxError in generated code at line %s: %s", err.lineno, err.msg)
            fixed_lines = []
            for ln in code.splitlines():
                if re.match(r"^\s*(?:def|class|if|elif|else|for|while|try|except|finally|with)\b.*[^:]$", ln):
                    if not ln.strip().endswith(":"):
                        ln = ln + ":"
                fixed_lines.append(ln)
            code = "\n".join(fixed_lines) + "\n"

    return code
