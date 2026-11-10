"""
Shared Data & Event Contracts (shared/models.py)
Mirrors Section 5 of Release Domino Team Guide (`shared/types.ts`).
Compatible with both Pydantic v1 and Pydantic v2.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

NodeKind = Literal["module", "route", "service", "view", "infra", "sandbox"]
NodeLang = Literal["py", "ts", "tsx", "js", "jsx", "other"]
NodeStatus = Literal["normal", "changed", "impacted", "failing"]
EdgeType = Literal["import", "call", "http", "infra"]
Verdict = Literal["GO", "CAUTION", "HOLD"]


class _CompatModel(BaseModel):
    def model_dump(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)  # type: ignore[misc]
        return self.dict(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ChurnInfo(_CompatModel):
    added: int = 0
    deleted: int = 0


class CNode(_CompatModel):
    id: str
    label: str
    path: str
    kind: NodeKind = "module"
    lang: NodeLang = "py"
    loc: int = 0
    churn: ChurnInfo = Field(default_factory=ChurnInfo)
    defect_score: float = 0.0
    coverage: Optional[float] = None
    coverage_estimated: bool = True
    is_crown_jewel: bool = False
    status: NodeStatus = "normal"
    risk: float = 0.0
    exports: List[str] = Field(default_factory=list)
    group: Optional[str] = None
    pos: Optional[Dict[str, float]] = None
    depth: Optional[int] = None
    impact: Optional[float] = None


class CEdge(_CompatModel):
    id: str
    source: str
    target: str
    type: EdgeType = "import"
    weight: float = 1.0


class Graph(_CompatModel):
    project_id: str
    nodes: List[CNode] = Field(default_factory=list)
    edges: List[CEdge] = Field(default_factory=list)


class DiffHunk(_CompatModel):
    start: int
    end: int


class FileDiff(_CompatModel):
    path: str
    added: int
    deleted: int
    hunks: List[DiffHunk] = Field(default_factory=list)


class DiffResult(_CompatModel):
    files: List[FileDiff] = Field(default_factory=list)
    total_added: int = 0
    total_deleted: int = 0


class FileConflict(_CompatModel):
    path: str
    lines: List[Tuple[int, int]] = Field(default_factory=list)


class MergeResult(_CompatModel):
    clean: bool = True
    base: str = "origin/main"
    conflicts: List[FileConflict] = Field(default_factory=list)


class TestFailure(_CompatModel):
    test: str
    node_id: Optional[str] = None
    message: str


class TestRunResult(_CompatModel):
    run_id: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    duration_s: float = 0.0
    coverage: Dict[str, float] = Field(default_factory=dict)
    failures: List[TestFailure] = Field(default_factory=list)
    selected_tests: Optional[int] = None
    total_tests: Optional[int] = None
    output: str = ""


class DiffFactorEntry(_CompatModel):
    name: str
    value: float
    weight: float
    contribution: float


class ImpactedNode(_CompatModel):
    id: str
    impact: float
    depth: int


class RiskResult(_CompatModel):
    score: float
    verdict: Verdict
    factors: List[DiffFactorEntry] = Field(default_factory=list)
    changed_nodes: List[str] = Field(default_factory=list)
    impacted: List[ImpactedNode] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    coverage_estimated: bool = True
    computed_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    baseline_score: Optional[float] = None
    baseline_verdict: Optional[Verdict] = None
    test_penalty: float = 0.0
    merge_penalty: float = 0.0


class EventEnvelope(_CompatModel):
    type: str
    project_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))


class TerminalMessage(_CompatModel):
    stream: Literal["stdout", "stderr", "system"] = "stdout"
    data: str
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
