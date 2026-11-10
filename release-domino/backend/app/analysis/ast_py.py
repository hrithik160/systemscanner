"""
Task B3 — Python AST Analyzer (backend/app/analysis/ast_py.py)
Extracts imports, exported functions/classes, FastAPI/Flask route decorators,
and backing infrastructure references from Python source files using stdlib `ast`.
"""
from __future__ import annotations

import ast
import re
from typing import Dict, List, Set, Tuple


def analyze_python_source(code: str, rel_path: str = "") -> Dict[str, object]:
    imports: List[str] = []
    exports: List[str] = []
    routes: List[str] = []
    infra: Set[str] = set()

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                for alias in node.names:
                    if node.module:
                        imports.append(f"{node.module}.{alias.name}")
                    else:
                        imports.append(alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                    if any(v in dec_str for v in (".get(", ".post(", ".put(", ".delete(", ".route(")):
                        routes.append(node.name)

        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not stmt.name.startswith("_"):
                    exports.append(stmt.name)
    except SyntaxError:
        imports = re.findall(r"(?:^|\n)\s*(?:import|from)\s+([a-zA-Z0-9_.]+)", code)
        exports = re.findall(r"(?:^|\n)\s*(?:async\s+)?(?:def|class)\s+([a-zA-Z0-9_]+)", code)

    low_code = code.lower()
    if "redis" in low_code or any("redis" in imp.lower() for imp in imports):
        infra.add("infra:redis")
    if any(k in low_code for k in ("psycopg", "postgres", "sqlalchemy", "asyncpg")):
        infra.add("infra:postgres")
    elif "sqlite" in low_code or "db" in rel_path.lower():
        infra.add("infra:sqlite")

    return {
        "imports": sorted(set(imports)),
        "exports": exports[:15],
        "routes": routes,
        "infra": sorted(infra),
        "loc": max(1, len(code.splitlines())),
    }
