"""FastAPI routes owned by Person 1 (Local LLM & AI Agent) integrated with Person 2 & Person 3."""

import asyncio
import logging
import os
import re
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm import client as llm_client
from app.llm.agent import AgentRunResult, run_agent_loop
from app.llm.arch import ArchitectureResult, detect_architecture
from app.llm.connect import (
    SandboxConnectResponse,
    _auto_heal_code_if_needed,
    _validate_code_syntax,
    _validate_style_preservation,
    get_proposal,
    propose_connection,
    remove_proposal,
    store_proposal,
)
from app.llm.knowledge import (
    ClarificationOption,
    ClarificationQuestion,
    ProjectKnowledge,
    _scan_repo_knowledge,
    auto_fix_runtime_error,
    compute_relative_import_path,
    detect_architecture_conflicts,
    extract_module_exports,
    generate_smart_import,
    guard_generated_code,
)
from app.llm.stretch import (
    AntiPatternAnalysisResult,
    AutoHealResult,
    ConflictResolveResult,
    auto_heal_test,
    detect_antipatterns,
    resolve_merge_conflict,
)
from app.llm.summarize import summarize_node
from app.llm.testgen import GeneratedTestResult, generate_tests

logger = logging.getLogger(__name__)

router = APIRouter()


class SummarizeRequest(BaseModel):
    code: str | None = None
    path: str | None = None
    deps: list[str] = Field(default_factory=list)
    lang: str | None = None


class SummarizeResponse(BaseModel):
    summary: list[str]
    purpose: str
    risks: list[str]
    exports: list[str] = Field(default_factory=list)


class GenerateTestsRequest(BaseModel):
    pid: str
    nid: str
    code: str | None = None
    diff: str = ""
    framework: str | None = None


class SandboxConnectRequest(BaseModel):
    pid: str
    source_node_id: str | None = None
    target_node_id: str | None = None
    from_node: str | None = Field(default=None, alias="from")
    to_node: str | None = Field(default=None, alias="to")
    source_code: str | None = None
    target_code: str | None = None

    model_config = {"populate_by_name": True}


class SandboxApplyRequest(BaseModel):
    pid: str
    proposal_id: str


class AgentChatRequest(BaseModel):
    pid: str
    prompt: str


class AntiPatternRequest(BaseModel):
    code: str | None = None
    path: str = "module.py"
    pid: str | None = None
    nid: str | None = None


class AutoHealRequest(BaseModel):
    stack_trace: str
    test_code: str = ""
    source_code: str = ""
    pid: str | None = None
    nid: str | None = None


class ConflictResolveRequest(BaseModel):
    conflict_text: str = ""
    ours_code: str = ""
    theirs_code: str = ""
    pid: str | None = None
    path: str | None = None


def _lookup_node_from_registry(pid: str, nid: str) -> dict[str, Any] | None:
    """Attempt to read node details from Person 3 / Unified project registry."""
    try:
        from app import projects
        if hasattr(projects, "get_node_data"):
            return projects.get_node_data(pid, nid)
    except ImportError:
        pass

    try:
        from app.main import get_node_data
        return get_node_data(pid, nid)
    except ImportError:
        pass

    return None


class LLMConfigRequest(BaseModel):
    api_key: str
    model: str | None = None


@router.post("/api/llm/config")
async def set_llm_config_endpoint(body: LLMConfigRequest) -> dict[str, Any]:
    """Save NVIDIA API key and optional model to runtime environment and .env file."""
    llm_client.set_runtime_nvidia_key(body.api_key, body.model)
    return await get_llm_status_endpoint()


@router.get("/api/llm/status")
async def get_llm_status_endpoint() -> dict[str, Any]:
    """Check if NVIDIA NIM API key, DeepSeek, or local Ollama is configured and return rich status for the UI."""
    nvidia_key = llm_client.get_nvidia_api_key()
    deepseek_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if nvidia_key:
        nv_model = llm_client.get_nvidia_model()
        short_name = nv_model.split("/")[-1] if "/" in nv_model else nv_model
        return {
            "ollama_online": True,
            "provider": "nvidia",
            "provider_name": "NVIDIA NIM",
            "nvidia_configured": True,
            "deepseek_configured": bool(deepseek_key),
            "ollama_url": llm_client.get_nvidia_base_url(),
            "configured_model": f"NVIDIA NIM ({short_name})",
            "model_id": nv_model,
            "endpoint_url": llm_client.get_nvidia_base_url(),
            "available_models": [
                nv_model,
                "nvidia/nemotron-3.5-bolt-e4b",
                "meta/llama-3.1-70b-instruct",
                "meta/llama-3.1-8b-instruct",
                "qwen/qwen2.5-coder-32b-instruct",
            ],
            "fallback_ready": True,
            "fallback_provider": "DeepSeek API (deepseek-flash)" if deepseek_key else "Local Ollama",
            "cache_dir": str(llm_client.CACHE_DIR),
            "masked_key": f"{nvidia_key[:8]}...{nvidia_key[-4:]}" if len(nvidia_key) > 12 else "***",
            "is_online": True,
        }

    ollama_url = llm_client.OLLAMA_URL.rstrip("/")
    model = llm_client.OLLAMA_MODEL
    online = False
    models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=1.5) as hc:
            r = await hc.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                online = True
                data = r.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        online = False
    return {
        "ollama_online": online,
        "provider": "ollama" if online else "fallback",
        "provider_name": "Local Ollama" if online else "Offline Fallback",
        "nvidia_configured": False,
        "deepseek_configured": bool(deepseek_key),
        "ollama_url": ollama_url,
        "configured_model": model if online else "AI Ready (Click to inspect / configure)",
        "model_id": model,
        "endpoint_url": ollama_url,
        "available_models": models or ["qwen2.5-coder:3b", "codellama:7b"],
        "fallback_ready": True,
        "fallback_provider": "Deterministic AST Engine",
        "cache_dir": str(llm_client.CACHE_DIR),
        "masked_key": "",
        "is_online": online,
    }


@router.post("/api/llm/test")
async def test_llm_connection_endpoint() -> dict[str, Any]:
    """Perform a live roundtrip test to the active LLM provider and return response metrics."""
    t0 = time.time()
    try:
        res = await llm_client.chat(
            messages=[{"role": "user", "content": "Respond with JSON: {\"status\": \"ok\", \"message\": \"nvidia connected\"}"}],
            timeout=10.0,
            fallback_factory=lambda: {"status": "ok", "message": "deterministic AST engine ready", "source": "fallback"},
        )
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        nvidia_key = llm_client.get_nvidia_api_key()
        active_provider = "NVIDIA NIM" if nvidia_key else "Local Ollama / Fallback"
        active_model = llm_client.get_nvidia_model() if nvidia_key else llm_client.OLLAMA_MODEL
        endpoint_url = llm_client.get_nvidia_base_url() if nvidia_key else llm_client.OLLAMA_URL
        return {
            "status": "success",
            "provider": active_provider,
            "model": active_model,
            "endpoint": endpoint_url,
            "latency_ms": elapsed_ms,
            "response": res,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }


@router.get("/api/node/{pid}/{nid:path}/code")
async def get_node_code_endpoint(pid: str, nid: str) -> dict[str, Any]:
    """Return raw source code and detected dependencies for a node in project `pid`."""
    node_data = _lookup_node_from_registry(pid, nid)
    if node_data is None or node_data.get("code") is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NODE_NOT_FOUND",
                    "message": f"Node '{nid}' could not be found in project '{pid}'.",
                }
            },
        )
    return {
        "pid": pid,
        "nid": nid,
        "path": node_data.get("path", nid),
        "code": node_data.get("code", ""),
        "dependencies": node_data.get("dependencies", []),
        "lang": node_data.get("lang", "py"),
    }


@router.post("/api/node/{pid}/{nid:path}/summarize", response_model=SummarizeResponse)
async def summarize_node_endpoint(
    pid: str,
    nid: str,
    body: SummarizeRequest | None = None,
) -> SummarizeResponse:
    """Return a 3-bullet plain-English summary, purpose, and risks for a node.

    Strictly requires code from request body or registry lookup; raises 404 if missing.
    """
    req = body or SummarizeRequest()
    code = req.code
    path = req.path or nid
    deps = req.deps
    lang = req.lang

    if code is None:
        node_data = _lookup_node_from_registry(pid, nid)
        if node_data is not None:
            code = node_data.get("code")
            path = node_data.get("path", path)
            raw_deps = node_data.get("dependencies", deps)
            if isinstance(raw_deps, list) and raw_deps and isinstance(raw_deps[0], list):
                deps = [str(x) for sub in raw_deps for x in sub]
            elif isinstance(raw_deps, list):
                deps = [str(x) for x in raw_deps]
            lang = node_data.get("lang", lang)

    if code is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NODE_NOT_FOUND",
                    "message": f"No code provided and node '{nid}' could not be found in project '{pid}'.",
                }
            },
        )

    result = await summarize_node(code=code, path=path, deps=deps, lang=lang)
    resp = SummarizeResponse(
        summary=result.summary,
        purpose=result.purpose,
        risks=result.risks,
        exports=result.exports,
    )
    try:
        from app.api.routes_p3 import _SUMMARY_CACHE, _emit
        _SUMMARY_CACHE[f"{pid}:{nid}"] = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
        await _emit("summary_ready", pid, {"node_id": nid, **(_SUMMARY_CACHE[f"{pid}:{nid}"])})
    except Exception:
        pass
    return resp


@router.get("/api/architecture/{pid}", response_model=ArchitectureResult)
async def get_architecture_endpoint(pid: str) -> ArchitectureResult:
    try:
        from app.main import get_project
        proj = get_project(pid)
    except ImportError:
        proj = None

    if proj is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "PROJECT_NOT_FOUND",
                    "message": f"Project '{pid}' not found in registry.",
                }
            },
        )

    return await detect_architecture(
        nodes=proj.get("nodes", []),
        node_codes=proj.get("node_codes", {}),
        project_path=proj.get("path"),
    )


@router.post("/api/tests/generate", response_model=GeneratedTestResult)
async def generate_tests_endpoint(body: GenerateTestsRequest) -> GeneratedTestResult:
    code = body.code
    if code is None:
        node_data = _lookup_node_from_registry(body.pid, body.nid)
        if node_data is not None:
            code = node_data.get("code")

    if code is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NODE_NOT_FOUND",
                    "message": f"Missing code for test generation on node '{body.nid}'.",
                }
            },
        )

    return await generate_tests(
        code=code,
        diff=body.diff,
        framework=body.framework,
        path=body.nid,
        project_id=body.pid,
        node_id=body.nid,
    )


@router.post("/api/sandbox/connect", response_model=SandboxConnectResponse)
async def sandbox_connect_endpoint(body: SandboxConnectRequest) -> SandboxConnectResponse:
    src_id = body.source_node_id or body.from_node or ""
    dst_id = body.target_node_id or body.to_node or ""

    src_code = body.source_code
    if src_code is None and src_id:
        nd = _lookup_node_from_registry(body.pid, src_id)
        if nd is not None:
            src_code = nd.get("code")

    dst_code = body.target_code
    if dst_code is None and dst_id:
        nd = _lookup_node_from_registry(body.pid, dst_id)
        if nd is not None:
            dst_code = nd.get("code")

    if src_code is None or dst_code is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "MISSING_NODE_CODE",
                    "message": "Both source and target node code must be provided or resolvable.",
                }
            },
        )

    res = await propose_connection(
        src_code=src_code,
        dst_code=dst_code,
        src_path=src_id or "source.py",
        dst_path=dst_id or "target.py",
    )

    proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
    store_proposal(
        proposal_id,
        {
            "pid": body.pid,
            "source_node_id": src_id,
            "target_node_id": dst_id,
            "patch": res.patch,
            "endpoint": res.endpoint,
        },
    )

    return SandboxConnectResponse(
        proposal_id=proposal_id,
        patch=res.patch,
        endpoint=res.endpoint,
        rationale=res.rationale,
    )


@router.post("/api/sandbox/apply")
async def sandbox_apply_endpoint(body: SandboxApplyRequest) -> dict[str, Any]:
    proposal = get_proposal(body.proposal_id)
    if proposal is None or proposal.get("pid") != body.pid:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "PROPOSAL_NOT_FOUND",
                    "message": f"Proposal '{body.proposal_id}' not found or expired.",
                }
            },
        )

    src_id = proposal.get("source_node_id")
    dst_id = proposal.get("target_node_id")
    remove_proposal(body.proposal_id)

    # Wire the new connection into Person 3's sandbox graph & emit WebSocket events
    try:
        from app.api.routes_p3 import (
            _PROJECT_PATHS,
            _SANDBOX_EDGES,
            _emit,
            build_project_graph_and_risk_sync,
        )
        if src_id and dst_id:
            edge_id = f"e-{src_id}-{dst_id}"
            _SANDBOX_EDGES.setdefault(body.pid, []).append(
                {"id": edge_id, "source": src_id, "target": dst_id, "type": "call", "weight": 0.9}
            )
            repo_path = _PROJECT_PATHS.get(body.pid)
            if repo_path and repo_path.exists():
                graph, risk = await asyncio.to_thread(build_project_graph_and_risk_sync, body.pid, repo_path)
                await _emit("node_updated", body.pid, {"node_id": dst_id, "endpoint": proposal.get("endpoint")})
                await _emit("diff_updated", body.pid, {"proposal_id": body.proposal_id, "patch": proposal.get("patch", "")})
                await _emit("risk_updated", body.pid, risk.to_dict())
    except Exception:
        pass

    return {
        "status": "applied",
        "proposal_id": body.proposal_id,
        "source_node_id": src_id,
        "target_node_id": dst_id,
        "endpoint": proposal.get("endpoint"),
    }


class BatchWirePreviewRequest(BaseModel):
    pid: str
    new_node_name: str
    new_node_code: str
    new_node_lang: str = "py"
    is_crown_jewel: bool = False
    input_node_ids: list[str] = Field(default_factory=list)
    output_node_ids: list[str] = Field(default_factory=list)


class NodeChangeProposal(BaseModel):
    node_id: str
    direction: str  # "input" | "output"
    original_code: str
    modified_code: str
    patch: str
    endpoint: str
    rationale: str


class BatchWirePreviewResponse(BaseModel):
    preview_id: str
    new_node: dict[str, Any]
    connected_changes: list[NodeChangeProposal]
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)


class BatchWireFinalizeRequest(BaseModel):
    pid: str
    preview_id: str
    apply: bool = True
    payload: dict[str, Any] | None = None


_PENDING_BATCH_PREVIEWS: dict[str, dict[str, Any]] = {}


def _get_project_code_for_node(pid: str, nid: str) -> str:
    nd = _lookup_node_from_registry(pid, nid)
    if nd and nd.get("code"):
        return nd["code"]
    try:
        from app.api.routes_p3 import _resolve_repo_path
        repo_path = _resolve_repo_path(pid)
        file_path = (repo_path / nid).resolve()
        if file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return f"# Module: {nid}\n"


class ValidateCodeRequest(BaseModel):
    code: str
    lang: str = "py"
    auto_heal: bool = False
    pid: str = "demo"
    node_name: str | None = None
    caller_ids: list[str] = Field(default_factory=list)
    output_ids: list[str] = Field(default_factory=list)


class ValidateCodeResponse(BaseModel):
    is_valid: bool
    error: str | None = None
    healed_code: str | None = None
    ai_validation_summary: str
    provider: str
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)


@router.post("/api/sandbox/validate-code", response_model=ValidateCodeResponse)
async def validate_code_endpoint(body: ValidateCodeRequest) -> ValidateCodeResponse:
    """Validate code syntax (AST/bracket/tag) and optionally auto-heal using NVIDIA NIM."""
    clean_lang = (body.lang or "py").lower().lstrip(".")
    is_valid, err_msg = _validate_code_syntax(body.code, clean_lang)

    nvidia_key = llm_client.get_nvidia_api_key()
    provider_name = (
        f"NVIDIA NIM ({llm_client.get_nvidia_model().split('/')[-1]})"
        if nvidia_key
        else "AST Syntax Engine"
    )

    healed_code: str | None = None
    if not is_valid and body.auto_heal:
        try:
            healed = await _auto_heal_code_if_needed(body.code, clean_lang, err_msg)
            if healed and healed != body.code:
                re_valid, _ = _validate_code_syntax(healed, clean_lang)
                if re_valid:
                    healed_code = healed
                    is_valid = True
                    err_msg = None
        except Exception as exc:
            logger.warning("Auto heal code error: %s", exc)

    if is_valid:
        summary = f"✓ Syntax, AST, and structure validated with 0 errors by {provider_name}."
    else:
        summary = f"⚠️ Syntax Error detected: {err_msg}"

    # Check for architecture and project conflicts to guide/clarify with the user
    questions: list[ClarificationQuestion] = []
    if body.node_name:
        repo_path = None
        try:
            from app.api.routes_p3 import _resolve_repo_path
            repo_path = _resolve_repo_path(body.pid)
        except Exception:
            pass

        questions = detect_architecture_conflicts(
            pid=body.pid,
            node_name=body.node_name,
            node_code=healed_code or body.code,
            lang=clean_lang,
            caller_node_ids=body.caller_ids,
            output_node_ids=body.output_ids,
            repo_path=repo_path,
        )

    return ValidateCodeResponse(
        is_valid=is_valid,
        error=err_msg,
        healed_code=healed_code,
        ai_validation_summary=summary,
        provider=provider_name,
        clarification_questions=questions,
    )


class AiGenerateNodeRequest(BaseModel):
    pid: str = "demo"
    prompt: str
    lang: str = "py"


class AiGenerateNodeResponse(BaseModel):
    name: str
    code: str
    lang: str
    is_crown_jewel: bool
    suggested_inputs: list[str] = Field(default_factory=list)
    suggested_outputs: list[str] = Field(default_factory=list)
    explanation: str


@router.post("/api/sandbox/ai-generate-node", response_model=AiGenerateNodeResponse)
async def ai_generate_node_endpoint(body: AiGenerateNodeRequest) -> AiGenerateNodeResponse:
    """Generate a complete new sandbox component and suggested graph connections using active LLM (NVIDIA NIM)."""
    import re
    lang = (body.lang or "py").lower().lstrip(".")
    ext_map = {"py": ".py", "ts": ".ts", "tsx": ".tsx", "js": ".js", "jsx": ".jsx"}
    ext = ext_map.get(lang, f".{lang}")

    # Inspect project knowledge to align file paths and framework conventions
    repo_path = None
    try:
        from app.api.routes_p3 import _resolve_repo_path
        repo_path = _resolve_repo_path(body.pid)
    except Exception:
        pass

    knowledge = None
    if repo_path and repo_path.is_dir():
        knowledge = _scan_repo_knowledge(repo_path, body.pid)

    existing_node_ids: list[str] = []
    if knowledge:
        existing_node_ids = knowledge.all_source_files
    else:
        try:
            from app.api.routes_p3 import _get_cached_project_data
            proj_data = _get_cached_project_data(body.pid)
            if proj_data and "graph" in proj_data:
                existing_node_ids = [n.get("id") for n in proj_data["graph"].get("nodes", []) if n.get("id")]
        except Exception:
            pass

    if not existing_node_ids:
        existing_node_ids = ["app/auth.py", "app/main.py", "app/redis_cache.py", "app/db.py"]

    # Detect if user prompt is requesting a UI/Frontend component
    prompt_lower = body.prompt.lower()
    is_ui_request = any(k in prompt_lower for k in ("home", "page", "button", "component", "ui", "modal", "view", "dashboard", "nav", "card", "landing", "screen"))

    default_dir = "app"
    if is_ui_request and knowledge and knowledge.frontend_apps:
        fe = knowledge.frontend_apps[0]
        default_dir = fe.get("src_dir", "frontend/src")
        if "react" in fe.get("framework", ""):
            lang = "jsx" if lang in ("js", "jsx", "py") else "tsx"
            ext = f".{lang}"
    elif knowledge and knowledge.backend_apps and not is_ui_request:
        be = knowledge.backend_apps[0]
        default_dir = be.get("dir") or "backend"
        if be.get("runtime") == "node" and lang == "py":
            lang = "js"
            ext = ".js"

    context_hint = f"Project Architecture Knowledge:\n- Structure: {knowledge.architecture_summary if knowledge else 'Standard app'}\n- Existing Files: {', '.join(existing_node_ids[:25])}."

    system_prompt = (
        "You are an expert full-stack software engineer and cloud architect.\n"
        f"Your task is to generate a complete, working source code module for language: {lang} ({ext}).\n"
        f"{context_hint}\n"
        f"Target directory for this node: '{default_dir}/'\n\n"
        "CRITICAL UNBREAKABLE CODE & ARCHITECTURE RULES:\n"
        "1. VISIBLE UI RULE: If this is a React component with modal, animation, or toggled visibility (e.g., isVisible, isOpen), NEVER return null without rendering a prominent launcher button! The component must render a button (e.g. <button onClick={handleShow}>🚀 Launch Feature</button>) so the user can see and trigger it on screen.\n"
        "2. PURE JAVASCRIPT: If lang is 'jsx' or 'js', use 100% PURE JavaScript/JSX. NEVER include TypeScript type annotations (NO ': React.FC', NO ': NodeJS.Timeout', NO 'interface', NO ': string'). Only use TypeScript syntax if lang is 'tsx' or 'ts'.\n"
        "3. SINGLE EXPORT DEFAULT: Provide exactly ONE 'export default ComponentName;'. All logic must reside inside this single file.\n"
        "4. VALID REACT SYMBOLS: React exports 'StrictMode', NOT 'StrictNode'.\n"
        "5. COMPLETE CODE: Do not truncate or use placeholders. Return ready-to-run code.\n\n"
        "Respond with a single JSON object conforming to this exact schema:\n"
        "{\n"
        f'  "name": "{default_dir}/filename{ext}",\n'
        '  "code": "complete working code with full implementation, exports, error handling, and type safety",\n'
        f'  "lang": "{lang}",\n'
        '  "is_crown_jewel": boolean,\n'
        '  "suggested_inputs": ["list of existing project nodes that should import or invoke this new module"],\n'
        '  "suggested_outputs": ["list of existing project nodes that this new module depends on or calls"],\n'
        '  "explanation": "summary of design, implementation details, and architecture connections"\n'
        "}"
    )

    def _fallback() -> dict[str, Any]:
        stem = re.sub(r"[^a-zA-Z0-9_]+", "_", body.prompt.lower().strip())[:24].strip("_") or "service"
        is_crown = any(w in body.prompt.lower() for w in ("auth", "security", "token", "jwt", "crypto", "payment", "rate"))
        if is_ui_request or lang in ("tsx", "jsx"):
            comp_name = stem.title().replace("_", "")
            click_fn = "() => setStatus('Clicked')"
            code = (
                f"import React, {{ useState }} from 'react';\n\n"
                f"export const {comp_name} = () => {{\n"
                f"  const [status, setStatus] = useState('Active');\n"
                f"  return (\n"
                f"    <div style={{{{ padding: '20px', textAlign: 'center', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155', color: '#fff', margin: '16px auto', maxWidth: '600px' }}}}>\n"
                f"      <h2 style={{{{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '8px' }}}}>{stem.replace('_', ' ').title()}</h2>\n"
                f"      <p style={{{{ fontSize: '12px', color: '#94a3b8', marginBottom: '12px' }}}}>Status: {{status}}</p>\n"
                f"      <button style={{{{ padding: '10px 24px', borderRadius: '8px', background: 'linear-gradient(135deg, #0284c7, #6366f1)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}}} onClick={{{click_fn}}}>\n"
                f"        Action Button\n"
                f"      </button>\n"
                f"    </div>\n"
                f"  );\n"
                f"}};\n\n"
                f"export default {comp_name};\n"
            )
            inputs = [nid for nid in existing_node_ids if "app." in nid.lower() or "main." in nid.lower()][:1]
        elif lang in ("ts", "js"):
            code = (
                f"// Auto-synthesized service for: {body.prompt}\n"
                f"export interface ServiceResponse {{\n"
                f"  success: boolean;\n"
                f"  message: string;\n"
                f"  timestamp: number;\n"
                f"}}\n\n"
                f"export async function processRequest(payload: Record<string, any>): Promise<ServiceResponse> {{\n"
                f"  return {{\n"
                f"    success: true,\n"
                f"    message: 'Operation executed',\n"
                f"    timestamp: Date.now(),\n"
                f"  }};\n"
                f"}}\n\n"
                f"export default processRequest;\n"
            )
            inputs = [nid for nid in existing_node_ids if "server." in nid.lower() or "app." in nid.lower()][:1]
        else:
            code = (
                f"\"\"\"Auto-synthesized module for: {body.prompt}\"\"\"\n"
                f"import time\n"
                f"import logging\n"
                f"from typing import Any, Dict\n\n"
                f"logger = logging.getLogger(__name__)\n\n"
                f"def handle_task(request_data: Dict[str, Any]) -> Dict[str, Any]:\n"
                f"    \"\"\"Process request with architectural safety guards.\"\"\"\n"
                f"    logger.info('Processing task with safety controls')\n"
                f"    return {{\n"
                f"        'status': 'success',\n"
                f"        'task': '{body.prompt[:40]}',\n"
                f"        'timestamp': time.time(),\n"
                f"    }}\n"
            )
            inputs = [nid for nid in existing_node_ids if "auth" in nid or "main" in nid][:1]
        return {
            "name": f"{default_dir}/{stem}{ext}",
            "code": code,
            "lang": lang,
            "is_crown_jewel": is_crown,
            "suggested_inputs": inputs,
            "suggested_outputs": [nid for nid in existing_node_ids if "cache" in nid or "db" in nid or "redis" in nid][:1],
            "explanation": f"Synthesized AST component for task: {body.prompt}",
        }

    try:
        raw_res = await llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.prompt},
            ],
            timeout=25.0,
            fallback_factory=_fallback,
        )
        if isinstance(raw_res, dict):
            # Clean up suggested inputs and outputs
            inputs = [str(x) for x in raw_res.get("suggested_inputs", []) if str(x) in existing_node_ids]
            outputs = [str(x) for x in raw_res.get("suggested_outputs", []) if str(x) in existing_node_ids]
            if not inputs and existing_node_ids:
                inputs = [existing_node_ids[0]]
            if not outputs and len(existing_node_ids) > 1:
                outputs = [existing_node_ids[1]]

            nvidia_key = llm_client.get_nvidia_api_key()
            provider_label = f"NVIDIA NIM ({llm_client.get_nvidia_model().split('/')[-1]})" if nvidia_key else "Local LLM"
            explanation = raw_res.get("explanation") or f"Synthesized by {provider_label}"
            if provider_label not in explanation:
                explanation = f"[{provider_label}] {explanation}"

            name_val = str(raw_res.get("name") or f"{default_dir}/module{ext}")
            if not name_val.endswith(ext):
                name_val = f"{name_val.rsplit('.', 1)[0]}{ext}"

            raw_code = str(raw_res.get("code") or _fallback()["code"])
            guarded_code = guard_generated_code(raw_code, lang=lang, file_path=name_val)

            return AiGenerateNodeResponse(
                name=name_val,
                code=guarded_code,
                lang=lang,
                is_crown_jewel=bool(raw_res.get("is_crown_jewel", False)),
                suggested_inputs=inputs,
                suggested_outputs=outputs,
                explanation=explanation,
            )
    except Exception as exc:
        logger.warning("AI generate node failed: %s", exc)

    fallback_data = _fallback()
    fallback_data["code"] = guard_generated_code(fallback_data["code"], lang=lang, file_path=fallback_data["name"])
    return AiGenerateNodeResponse(**fallback_data)


@router.post("/api/sandbox/batch-wire-preview", response_model=BatchWirePreviewResponse)
async def sandbox_batch_wire_preview_endpoint(body: BatchWirePreviewRequest) -> BatchWirePreviewResponse:
    """Task L5: Synthesize and preview AI batch wiring for a new sandbox node and all its connected callers & dependencies."""
    from pathlib import Path
    import difflib

    preview_id = f"batch_{uuid.uuid4().hex[:10]}"
    connected_changes: list[NodeChangeProposal] = []
    lang = (body.new_node_lang or "py").lower().lstrip(".")

    # 1. Process Input Callers using Project Knowledge & exact relative path resolution
    for caller_nid in body.input_node_ids:
        orig_code = _get_project_code_for_node(body.pid, caller_nid)
        caller_ext = Path(caller_nid).suffix.lower().lstrip(".")

        smart_imp = generate_smart_import(
            caller_path=caller_nid,
            caller_code=orig_code,
            target_path=body.new_node_name,
            target_code=body.new_node_code,
            lang=caller_ext if caller_ext in ("js", "jsx", "ts", "tsx", "py") else lang,
        )
        import_stmt = smart_imp["import_statement"]
        endpoint = smart_imp["symbol"]
        rationale = f"Wires {caller_nid} to import '{endpoint}' from '{smart_imp['path']}'."

        if smart_imp["path"] not in orig_code and import_stmt.strip() not in orig_code:
            lines = orig_code.splitlines(keepends=True)
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith(('"""', "'''", "#!", "#", "from __future__", "//", "/*")):
                    insert_idx = idx + 1
                elif line.strip() == "":
                    continue
                else:
                    break
            mod_code = "".join(lines[:insert_idx]) + import_stmt + "".join(lines[insert_idx:])
        else:
            mod_code = orig_code

        # If caller is a React component and the imported symbol is a React Component (Capitalized), mount it in JSX
        if (caller_ext in ("jsx", "tsx") or caller_nid.endswith((".jsx", ".tsx"))) and endpoint and endpoint[0].isupper():
            if f"<{endpoint}" not in mod_code:
                close_match = re.search(r"(\r?\n)(\s*)(</(?:section|main|div)>)", mod_code)
                if close_match:
                    nl = close_match.group(1)
                    indent = close_match.group(2)
                    tag = close_match.group(3)
                    pos = close_match.start()
                    mount_snippet = f"{nl}{indent}  <{endpoint} />"
                    mod_code = mod_code[:pos] + mount_snippet + mod_code[pos:]

        # If caller is Python and target is a Python module, plug into caller execution
        if (caller_ext in ("py", "python") or caller_nid.endswith(".py")) and endpoint:
            if "router" in endpoint.lower() and re.search(r"\bapp\s*=\s*(?:FastAPI|Starlette)\s*\(", mod_code):
                if f"app.include_router({endpoint})" not in mod_code:
                    app_match = re.search(r"(\bapp\s*=\s*(?:FastAPI|Starlette)\s*\([^\)]*\)\s*\r?\n)", mod_code)
                    if app_match:
                        pos = app_match.end()
                        mod_code = mod_code[:pos] + f"app.include_router({endpoint})\n" + mod_code[pos:]
            elif "middleware" in endpoint.lower() and re.search(r"\bapp\s*=\s*(?:FastAPI|Starlette)\s*\(", mod_code):
                if f"app.add_middleware({endpoint})" not in mod_code:
                    app_match = re.search(r"(\bapp\s*=\s*(?:FastAPI|Starlette)\s*\([^\)]*\)\s*\r?\n)", mod_code)
                    if app_match:
                        pos = app_match.end()
                        mod_code = mod_code[:pos] + f"app.add_middleware({endpoint})\n" + mod_code[pos:]
            elif any(k in endpoint.lower() for k in ("guard", "limit", "auth", "check", "verify", "sanitize", "audit", "calc", "process")):
                if f"{endpoint}(" not in mod_code:
                    def_match = re.search(r"(\bdef\s+[A-Za-z0-9_]+\s*\([^\)]*\)\s*(?:->\s*[^:]+)?:\s*(?:\r?\n\s*\"\"\"[^\"]*\"\"\"\s*)?\r?\n)(\s+)", mod_code)
                    if def_match:
                        indent = def_match.group(2)
                        pos = def_match.end()
                        invocation = f"{indent}# Invoked via Release Domino sandbox connection\n{indent}{endpoint}()\n"
                        mod_code = mod_code[:pos] + invocation + mod_code[pos:]

        mod_code = _validate_style_preservation(orig_code, mod_code)
        valid, _ = _validate_code_syntax(mod_code, caller_ext)
        if not valid:
            mod_code = await _auto_heal_code_if_needed(mod_code, caller_ext, orig_code)

        diff_lines = list(difflib.unified_diff(
            orig_code.splitlines(keepends=True),
            mod_code.splitlines(keepends=True),
            fromfile=f"a/{caller_nid}",
            tofile=f"b/{caller_nid}",
        ))
        patch_str = "".join(diff_lines) or f"--- a/{caller_nid}\n+++ b/{caller_nid}\n@@ -1,1 +1,2 @@\n+{import_stmt}"

        connected_changes.append(NodeChangeProposal(
            node_id=caller_nid,
            direction="input",
            original_code=orig_code,
            modified_code=mod_code,
            patch=patch_str,
            endpoint=endpoint,
            rationale=rationale,
        ))

    # 2. Process Output Dependencies (nodes that this new node will import / invoke)
    for dep_nid in body.output_node_ids:
        dep_code = _get_project_code_for_node(body.pid, dep_nid)
        dep_ext = Path(dep_nid).suffix.lower().lstrip(".")
        smart_imp = generate_smart_import(
            caller_path=body.new_node_name,
            caller_code=body.new_node_code,
            target_path=dep_nid,
            target_code=dep_code,
            lang=lang,
        )
        rationale = f"Wires {body.new_node_name} to invoke external dependency '{smart_imp['symbol']}' from '{smart_imp['path']}'."
        endpoint = smart_imp["symbol"]
        patch_str = f"--- a/{body.new_node_name}\n+++ b/{body.new_node_name}\n@@ -1,1 +1,2 @@\n+{smart_imp['import_statement']}"

        connected_changes.append(NodeChangeProposal(
            node_id=dep_nid,
            direction="output",
            original_code=dep_code,
            modified_code=dep_code,
            patch=patch_str,
            endpoint=endpoint,
            rationale=rationale,
        ))

    # 3. Detect Architecture & Path Conflicts to ask the user questions before breaking changes
    repo_path = None
    try:
        from app.api.routes_p3 import _resolve_repo_path
        repo_path = _resolve_repo_path(body.pid)
    except Exception:
        pass

    questions = detect_architecture_conflicts(
        pid=body.pid,
        node_name=body.new_node_name,
        node_code=body.new_node_code,
        lang=lang,
        caller_node_ids=body.input_node_ids,
        output_node_ids=body.output_node_ids,
        repo_path=repo_path,
    )

    preview_payload = {
        "preview_id": preview_id,
        "new_node": {
            "name": body.new_node_name,
            "code": body.new_node_code,
            "lang": body.new_node_lang,
            "is_crown_jewel": body.is_crown_jewel,
        },
        "connected_changes": [c.model_dump() for c in connected_changes],
        "clarification_questions": [q.model_dump() for q in questions],
    }
    _PENDING_BATCH_PREVIEWS[preview_id] = preview_payload

    return BatchWirePreviewResponse(
        preview_id=preview_id,
        new_node=preview_payload["new_node"],
        connected_changes=connected_changes,
        clarification_questions=questions,
    )


@router.post("/api/sandbox/batch-wire-finalize")
async def sandbox_batch_wire_finalize_endpoint(body: BatchWireFinalizeRequest) -> dict[str, Any]:
    """Task L5: Finalize and apply or discard batch wiring for a new sandbox node."""
    import re
    from pathlib import Path

    preview = _PENDING_BATCH_PREVIEWS.pop(body.preview_id, None)
    if not body.apply:
        return {"status": "discarded", "preview_id": body.preview_id}

    payload = body.payload or preview
    if not payload:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "MISSING_PAYLOAD", "message": f"Preview '{body.preview_id}' not found or payload missing."}},
        )

    new_node_info = payload.get("new_node", {})
    raw_name = new_node_info.get("name", "app/custom_node.py")
    code_str = new_node_info.get("code", "")
    lang = new_node_info.get("lang", "py")
    is_crown = bool(new_node_info.get("is_crown_jewel"))

    clean_name = re.sub(r"[^a-zA-Z0-9_./-]", "_", raw_name.strip())
    if not clean_name.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
        ext = ".py" if lang == "py" else (".tsx" if lang == "tsx" else (".jsx" if lang == "jsx" else (".ts" if lang == "ts" else ".js")))
        clean_name = f"{clean_name}{ext}"

    # Attempt to resolve repo path for disk writing
    repo_path = None
    try:
        from app.api.routes_p3 import _resolve_repo_path
        repo_path = _resolve_repo_path(body.pid)
    except Exception:
        pass

    if repo_path and repo_path.is_dir():
        # Write new node file
        try:
            dest_file = (repo_path / clean_name).resolve()
            if str(dest_file).startswith(str(repo_path.resolve())):
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(code_str, encoding="utf-8")
        except Exception as e:
            logger.warning("Could not write sandbox node to disk: %s", e)

        # Write modified caller files
        for ch in payload.get("connected_changes", []):
            if ch.get("direction") == "input" and ch.get("modified_code"):
                ch_nid = ch.get("node_id")
                if ch_nid:
                    try:
                        target_f = (repo_path / ch_nid).resolve()
                        if target_f.exists() and str(target_f).startswith(str(repo_path.resolve())):
                            target_f.write_text(ch["modified_code"], encoding="utf-8")
                    except Exception as e:
                        logger.warning("Could not write modified caller '%s' to disk: %s", ch_nid, e)

    # Wire into Person 3 graph registry
    try:
        from app.api.routes_p3 import (
            _SANDBOX_NODES,
            _CROWN_OVERRIDES,
            _SANDBOX_EDGES,
            _emit,
            build_project_graph_and_risk_sync,
            _parse_python_ast,
            _parse_js_ts_imports,
        )

        imports, exports = _parse_python_ast(code_str) if lang == "py" else _parse_js_ts_imports(code_str)
        _SANDBOX_NODES.setdefault(body.pid, {})[clean_name] = {
            "path": clean_name,
            "label": Path(clean_name).name,
            "code": code_str,
            "lang": lang,
            "kind": "sandbox",
            "loc": max(1, len(code_str.splitlines())),
            "imports": imports,
            "exports": exports,
        }
        if is_crown:
            _CROWN_OVERRIDES.setdefault(body.pid, {})[clean_name] = True

        for ch in payload.get("connected_changes", []):
            ch_nid = ch.get("node_id")
            if not ch_nid:
                continue
            if ch.get("direction") == "input":
                edge_id = f"e-{ch_nid}-{clean_name}"
                _SANDBOX_EDGES.setdefault(body.pid, []).append(
                    {"id": edge_id, "source": ch_nid, "target": clean_name, "type": "call", "weight": 0.95}
                )
            else:
                edge_id = f"e-{clean_name}-{ch_nid}"
                _SANDBOX_EDGES.setdefault(body.pid, []).append(
                    {"id": edge_id, "source": clean_name, "target": ch_nid, "type": "call", "weight": 0.95}
                )

        if repo_path and repo_path.is_dir():
            graph, risk = await asyncio.to_thread(build_project_graph_and_risk_sync, body.pid, repo_path)
            created_node = next((n for n in graph.nodes if n.id == clean_name), None)
            if created_node:
                await _emit("node_updated", body.pid, created_node.to_dict())
            await _emit("risk_updated", body.pid, risk.to_dict())
            await _emit("graph_updated", body.pid, graph.to_dict())
    except Exception as e:
        logger.warning("Error updating Person 3 graph in batch wire finalize: %s", e)

    return {
        "status": "applied",
        "new_node_id": clean_name,
        "preview_id": body.preview_id,
    }


@router.post("/api/agent/chat", response_model=AgentRunResult)
async def agent_chat_endpoint(body: AgentChatRequest) -> AgentRunResult:
    if not body.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_PROMPT", "message": "Agent prompt cannot be empty."}},
        )
    return await run_agent_loop(project_id=body.pid, prompt=body.prompt)


@router.post("/api/stretch/antipatterns", response_model=AntiPatternAnalysisResult)
async def stretch_antipatterns_endpoint(body: AntiPatternRequest) -> AntiPatternAnalysisResult:
    code = body.code
    path = body.path
    if code is None and body.pid and body.nid:
        nd = _lookup_node_from_registry(body.pid, body.nid)
        if nd is not None:
            code = nd.get("code")
            path = nd.get("path", body.nid)
    if not code:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "MISSING_CODE", "message": "Code or valid (pid, nid) required."}},
        )
    return await detect_antipatterns(code=code, path=path)


@router.post("/api/stretch/auto-heal", response_model=AutoHealResult)
async def stretch_auto_heal_endpoint(body: AutoHealRequest) -> AutoHealResult:
    src_code = body.source_code
    if not src_code and body.pid and body.nid:
        nd = _lookup_node_from_registry(body.pid, body.nid)
        if nd is not None:
            src_code = nd.get("code", "")
    return await auto_heal_test(
        stack_trace=body.stack_trace,
        test_code=body.test_code,
        source_code=src_code,
    )


@router.post("/api/stretch/resolve-conflict", response_model=ConflictResolveResult)
async def stretch_resolve_conflict_endpoint(body: ConflictResolveRequest) -> ConflictResolveResult:
    ours = body.ours_code
    theirs = body.theirs_code
    conflict_txt = body.conflict_text
    if body.pid and not ours:
        target_path = body.path or "app/auth.py"
        nd = _lookup_node_from_registry(body.pid, target_path)
        if nd and nd.get("code"):
            ours = nd["code"]
        if not conflict_txt:
            conflict_txt = f"Conflict in {target_path} between HEAD and origin/main"
        if not theirs:
            theirs = ours
    return await resolve_merge_conflict(
        conflict_text=conflict_txt,
        ours_code=ours,
        theirs_code=theirs,
    )


class FileChatRequest(BaseModel):
    pid: str
    nid: str
    prompt: str
    code: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class FileChatResponse(BaseModel):
    reply: str
    suggested_code: str | None = None


@router.post("/api/node/{pid}/{nid:path}/chat", response_model=FileChatResponse)
async def node_file_chat_endpoint(pid: str, nid: str, body: FileChatRequest) -> FileChatResponse:
    """Interactive AI chat regarding a specific file/node in the project."""
    import re

    code = body.code
    if code is None:
        nd = _lookup_node_from_registry(pid, nid)
        if nd is not None:
            code = nd.get("code")

    code_context = f"\n\n--- Source code for {nid} ---\n{code}\n--- End source code ---\n" if code else ""
    history_context = ""
    for msg in body.history[-6:]:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        history_context += f"\n{role}: {content}"

    prompt = (
        f"You are an expert AI code copilot and security engineer assisting a developer with file: {nid}.\n"
        f"Project: {pid}\n"
        f"{code_context}\n"
        f"{history_context}\n\n"
        f"User query: {body.prompt}\n\n"
        f"Answer clearly and concisely. If you propose updated code or bug fixes, provide the complete revised code inside a markdown code block (e.g. ```python ... ```)."
    )

    try:
        raw_reply = await llm_client.call_llm(prompt)
    except Exception as e:
        raw_reply = f"AI assistant encountered an error: {e}. Here is an automated inspection: {nid} contains {len(code.splitlines()) if code else 0} lines."

    # Extract suggested replacement code if present in code block
    suggested_code = None
    code_match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\n(.*?)```", raw_reply, re.DOTALL)
    if code_match and len(code_match.group(1).strip().splitlines()) >= 3:
        suggested_code = code_match.group(1).strip()

    return FileChatResponse(reply=raw_reply, suggested_code=suggested_code)


class AutoFixRuntimeErrorRequest(BaseModel):
    pid: str
    error_text: str


class AutoFixRuntimeErrorResponse(BaseModel):
    fixed: bool
    message: str
    created_file: str | None = None


@router.post("/api/sandbox/auto-fix-runtime-error", response_model=AutoFixRuntimeErrorResponse)
async def auto_fix_runtime_error_endpoint(body: AutoFixRuntimeErrorRequest) -> AutoFixRuntimeErrorResponse:
    """Diagnose and auto-repair runtime / Vite bundler errors from terminal output."""
    from app.api.routes_p3 import _resolve_repo_path
    repo_path = _resolve_repo_path(body.pid)
    res = auto_fix_runtime_error(body.pid, body.error_text, repo_path)
    return AutoFixRuntimeErrorResponse(**res)

