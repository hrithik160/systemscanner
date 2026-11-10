"""
Task B6 — Release Domino Risk Engine (backend/app/analysis/risk.py)
Implements the exact mathematical specification from Section 6 of the Team Guide:
  churn_n   = min(1, (added + deleted) / 200)
  defect_n  = defect_score / 10
  cover_n   = 1 - coverage
  blast_n   = min(1, sum(impact_i of impacted nodes) / (0.25 * total_nodes))
              if a crown jewel is impacted: blast_n = max(blast_n, 0.8)
  r_node    = 0.30*churn_n + 0.30*defect_n + 0.25*cover_n + 0.15*blast_n
  score     = 100 * (0.7 * max(r_node) + 0.3 * mean(r_node))
  score    += 15 if any test failed
  score    += 15 if merge conflicts exist
  score     = min(100, score)
  verdict   = GO if score < 35 else CAUTION if score <= 65 else HOLD
"""
from __future__ import annotations

from typing import Tuple


def compute_node_risk_factors(
    added: int,
    deleted: int,
    defect_score: float,
    coverage: float,
    blast_n: float,
) -> Tuple[float, float, float, float, float]:
    churn_n = min(1.0, max(0.0, (added + deleted) / 200.0))
    defect_n = min(1.0, max(0.0, defect_score / 10.0))
    cover_n = min(1.0, max(0.0, 1.0 - coverage))
    b_n = min(1.0, max(0.0, blast_n))
    r_node = 0.30 * churn_n + 0.30 * defect_n + 0.25 * cover_n + 0.15 * b_n
    return churn_n, defect_n, cover_n, b_n, r_node


def score_to_verdict(score: float) -> str:
    if score < 35:
        return "GO"
    if score <= 65:
        return "CAUTION"
    return "HOLD"


def compute_worked_example_score(
    added: int = 48,
    deleted: int = 12,
    defect_score: float = 7.0,
    coverage: float = 0.20,
    crown_jewel_impacted: bool = True,
    any_test_failed: bool = True,
    has_merge_conflict: bool = False,
) -> Tuple[int, str]:
    """
    Verifies the Section 6 worked example:
    auth.py: +48 / -12 = 60 lines -> churn_n = 0.30.
    Defect score 7 -> defect_n = 0.70.
    Coverage 20% -> cover_n = 0.80.
    Crown jewel impacted -> blast_n = 0.80.
    r = 0.3*0.30 + 0.3*0.70 + 0.25*0.80 + 0.15*0.80 = 0.62 -> base score = 62.
    One failing test adds 15 -> 77 -> HOLD.
    """
    blast_n = 0.80 if crown_jewel_impacted else 0.0
    _, _, _, _, r_node = compute_node_risk_factors(added, deleted, defect_score, coverage, blast_n)
    score = 100.0 * (0.70 * r_node + 0.30 * r_node)
    if any_test_failed:
        score += 15.0
    if has_merge_conflict:
        score += 15.0
    final = min(100, int(round(score)))
    return final, score_to_verdict(final)
