"""RunPlan: the single contract between the LLM planner, the validator and the executor."""
from __future__ import annotations

import shlex
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Lang = Literal["python", "node", "go", "rust", "java", "php", "ruby", "dotnet", "static", "other"]
Role = Literal["frontend", "backend", "fullstack", "worker", "database", "mobile", "library"]


def _to_argv(v):
    """The LLM may emit 'npm ci' or ['npm','ci']; always normalise to argv."""
    if isinstance(v, str):
        return shlex.split(v)
    return v


class Runtime(BaseModel):
    lang: Lang
    version: Optional[str] = None


class Readiness(BaseModel):
    type: Literal["http", "tcp", "none"] = "http"
    path: str = "/"
    timeout_s: int = Field(60, ge=1, le=180)


ReadinessProbe = Readiness


class Service(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    role: Role
    cwd: str = "."
    runtime: Optional[Runtime] = None
    install: list[list[str]] = Field(default_factory=list)   # argv arrays, network ON
    build: list[list[str]] = Field(default_factory=list)     # argv arrays, network ON
    start: list[str] = Field(default_factory=list)           # argv array, network OFF
    env: dict[str, str] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    readiness: Optional[Readiness] = Field(default_factory=Readiness)

    @field_validator("install", "build", mode="before")
    @classmethod
    def _steps(cls, v):
        return [_to_argv(s) for s in (v or [])]

    @field_validator("start", mode="before")
    @classmethod
    def _start(cls, v):
        return _to_argv(v) if v else []


ServiceSpec = Service


class RunPlan(BaseModel):
    runnable: bool = True
    reason: Optional[str] = None          # required when runnable is false
    reasoning: Optional[str] = None       # alias for reason
    services: list[Service] = Field(default_factory=list)
    entry_service: Optional[str] = None   # the service the preview/gateway opens
    confidence: float = Field(0.5, ge=0, le=1)
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self):
        if not self.reason and self.reasoning:
            self.reason = self.reasoning
        elif not self.reasoning and self.reason:
            self.reasoning = self.reason

        if not self.runnable:
            if not self.reason:
                raise ValueError("runnable=false requires a reason")
            return self

        names = [s.name for s in self.services]
        if not names:
            raise ValueError("runnable plan needs at least one service")
        if len(set(names)) != len(names):
            raise ValueError("duplicate service names")
        if self.entry_service not in names:
            raise ValueError("entry_service must name one of the services")
        for s in self.services:
            if s.role not in ("mobile", "library") and not s.start:
                raise ValueError(f"service '{s.name}' has no start command")
        return self


def topo_order(plan: RunPlan) -> list[Service]:
    """Start order: dependencies before dependants."""
    by_name = {s.name: s for s in plan.services}
    visited: set[str] = set()
    order: list[Service] = []

    def visit(name: str):
        if name in visited or name not in by_name:
            return
        visited.add(name)
        for dep in by_name[name].depends_on:
            visit(dep)
        order.append(by_name[name])

    for s in plan.services:
        visit(s.name)
    return order
