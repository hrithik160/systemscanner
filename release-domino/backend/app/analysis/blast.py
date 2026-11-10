"""
Task B5 — Blast Radius BFS over Reversed Edges (backend/app/analysis/blast.py)
Direction rule (Section 5 & Section 6):
  An edge source -> target means source depends on (imports) target.
  A change in a node impacts the nodes that depend on it, so impact travels along edges in reverse.
  impact(start) = 1.0
  impact(next) = impact(parent) * edge.weight * 0.85
  Stop below 0.1. Record depth for the shockwave animation.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Tuple

from shared.models import CEdge, ImpactedNode


def compute_blast_radius(
    edges: Iterable[CEdge],
    changed_ids: Iterable[str],
    decay: float = 0.85,
    min_impact: float = 0.10,
) -> List[ImpactedNode]:
    reverse_adj: Dict[str, List[Tuple[str, float]]] = {}
    for e in edges:
        reverse_adj.setdefault(e.target, []).append((e.source, float(e.weight)))

    best_impact: Dict[str, float] = {}
    best_depth: Dict[str, int] = {}
    queue: deque[Tuple[str, float, int]] = deque()

    for cid in changed_ids:
        best_impact[cid] = 1.0
        best_depth[cid] = 0
        queue.append((cid, 1.0, 0))

    while queue:
        curr_id, curr_impact, curr_depth = queue.popleft()
        for dep_id, weight in reverse_adj.get(curr_id, []):
            next_impact = round(curr_impact * weight * decay, 4)
            if next_impact < min_impact:
                continue
            next_depth = curr_depth + 1
            if next_impact > best_impact.get(dep_id, 0.0):
                best_impact[dep_id] = next_impact
                best_depth[dep_id] = min(best_depth.get(dep_id, next_depth), next_depth)
                queue.append((dep_id, next_impact, next_depth))

    impacted_list = [
        ImpactedNode(id=nid, impact=round(imp, 2), depth=best_depth[nid])
        for nid, imp in best_impact.items()
    ]
    impacted_list.sort(key=lambda x: (x.depth, -x.impact, x.id))
    return impacted_list
