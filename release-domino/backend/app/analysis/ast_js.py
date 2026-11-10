"""
Task B3 — JavaScript / TypeScript Import & Route Scanner (backend/app/analysis/ast_js.py)
Scans ES6 `import ... from`, CommonJS `require(...)`, dynamic `import(...)`, exported symbols,
and Express/React route patterns.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\))"""
)
JS_EXPORT_RE = re.compile(
    r"""export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z0-9_$]+)"""
)
EXPRESS_ROUTE_RE = re.compile(r"""\b(?:app|router)\.(get|post|put|delete|patch)\(\s*['"]([^'"]+)['"]""")


def analyze_js_ts_source(code: str, rel_path: str = "") -> Dict[str, object]:
    imports: List[str] = []
    for m in JS_IMPORT_RE.finditer(code):
        imp = m.group(1) or m.group(2) or m.group(3)
        if imp:
            imports.append(imp)

    exports = [m.group(1) for m in JS_EXPORT_RE.finditer(code)]
    routes = [f"{m.group(1).upper()} {m.group(2)}" for m in EXPRESS_ROUTE_RE.finditer(code)]

    infra: Set[str] = set()
    low = code.lower()
    if "redis" in low or "ioredis" in low:
        infra.add("infra:redis")
    if any(k in low for k in ("pg", "postgres", "prisma", "typeorm", "sequelize")):
        infra.add("infra:postgres")

    return {
        "imports": sorted(set(imports)),
        "exports": exports[:15],
        "routes": routes,
        "infra": sorted(infra),
        "loc": max(1, len(code.splitlines())),
    }
