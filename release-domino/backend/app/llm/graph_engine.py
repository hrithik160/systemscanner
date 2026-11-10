"""
Deterministic Graph Engine & Verified Proposal Loop (app/llm/graph_engine.py).
Python port of graph-engine.ts using Pydantic.
Enforces:
1. Typed Port Contracts on Nodes (inputs/outputs).
2. Structured Atomic Operations DSL (add_node, update_node, remove_node, add_edge, remove_edge).
3. Deterministic Validation (nodes exist, ports exist, type compatibility, fan-in, cycles, AST parse).
4. Deterministic Impact-Set Traversal (BFS neighbors).
5. Explicit Neighbor Review Enforcement (NEIGHBOR_NOT_REVIEWED).
6. 3-Try Diagnostic Feedback Retry Loop with Atomic Rollback on failure.
"""
from __future__ import annotations

import ast
import copy
import json
import logging
import re
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ================= 1. SCHEMA =================

class Port(BaseModel):
    name: str
    type: str
    required: bool = True


class PortRef(BaseModel):
    node: str
    port: str


class CNode(BaseModel):
    id: str
    name: str
    language: str
    code: str
    inputs: List[Port] = Field(default_factory=list)
    outputs: List[Port] = Field(default_factory=list)
    path: Optional[str] = None
    is_crown_jewel: bool = False


class CEdge(BaseModel):
    id: str
    from_port: PortRef = Field(alias="from")
    to_port: PortRef = Field(alias="to")

    class Config:
        populate_by_name = True


class Graph(BaseModel):
    nodes: Dict[str, CNode] = Field(default_factory=dict)
    edges: List[CEdge] = Field(default_factory=list)


# Operation definitions
class AddNodeOp(BaseModel):
    op: Literal["add_node"]
    node: CNode


class UpdateNodeOp(BaseModel):
    op: Literal["update_node"]
    node: CNode


class RemoveNodeOp(BaseModel):
    op: Literal["remove_node"]
    id: str


class AddEdgeOp(BaseModel):
    op: Literal["add_edge"]
    id: str
    from_port: PortRef = Field(alias="from")
    to_port: PortRef = Field(alias="to")

    class Config:
        populate_by_name = True


class RemoveEdgeOp(BaseModel):
    op: Literal["remove_edge"]
    id: str


class ReviewedNode(BaseModel):
    nodeId: str
    action: Literal["updated", "no_change"]
    reason: str


class Proposal(BaseModel):
    ops: List[Dict[str, Any]]
    reviewed: List[ReviewedNode]


class Diag(BaseModel):
    code: str
    message: str
    nodeId: Optional[str] = None
    edgeId: Optional[str] = None


# ================= 2. VALIDATOR =================

def default_type_compatible(out_type: str, in_type: str) -> bool:
    """Type compatibility matrix across languages and runtimes."""
    if out_type == in_type or in_type == "any" or out_type == "any":
        return True

    # React / UI subtyping
    if out_type in ("ReactComponent", "JSX.Element") and in_type in ("ReactComponent", "JSX.Element", "ReactNode"):
        return True

    # API / HTTP subtyping
    if out_type in ("HTTP_Endpoint", "FastAPIRoute", "ExpressRoute") and in_type in ("HTTP_Client", "JSON_API"):
        return True

    # Python callable / middleware subtyping
    if out_type in ("PythonCallable", "Function") and in_type in ("PythonCallable", "Function", "Middleware"):
        return True

    # Reject crossing language/runtime boundaries without bridge
    if "Python" in out_type and "React" in in_type:
        return False

    return False


def default_parse_check(node: CNode) -> Optional[str]:
    """Parse check per language: Python via ast.parse, JS/TS via bracket balance."""
    code = node.code or ""
    if not code.strip():
        return None

    lang = (node.language or "py").lower()
    if lang in ("py", "python"):
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return f"Python SyntaxError at line {e.lineno}: {e.msg}"

    if lang in ("js", "jsx", "ts", "tsx"):
        # Framework hallucination check (e.g. StrictNode instead of StrictMode)
        if re.search(r"\bStrictNode\b", code):
            return "Invalid symbol 'StrictNode' from 'react'. React exports 'StrictMode'."

        # Bracket balancing
        stack = []
        pairs = {")": "(", "}": "{", "]": "["}
        openers = set(pairs.values())
        for idx, ch in enumerate(code, start=1):
            if ch in openers:
                stack.append((ch, idx))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    return f"Unbalanced '{ch}' at char {idx}"
                stack.pop()
        if stack:
            return f"Unclosed '{stack[-1][0]}' opened at char {stack[-1][1]}"

    return None


def validate_graph(
    g: Graph,
    type_compatible: Callable[[str, str], bool] = default_type_compatible,
    parse_check: Callable[[CNode], Optional[str]] = default_parse_check,
) -> List[Diag]:
    """Deterministic validation: nodes exist, ports exist, types match, fan-in <= 1, required inputs, cycles, AST syntax."""
    diags: List[Diag] = []

    def get_port(n: Optional[CNode], port_name: str, side: str) -> Optional[Port]:
        if not n:
            return None
        ports = n.inputs if side == "inputs" else n.outputs
        for p in ports:
            if p.name == port_name:
                return p
        return None

    in_count: Dict[str, int] = {}

    for e in g.edges:
        from_node_id = e.from_port.node
        to_node_id = e.to_port.node
        from_node = g.nodes.get(from_node_id)
        to_node = g.nodes.get(to_node_id)

        if not from_node:
            diags.append(Diag(code="NODE_MISSING", edgeId=e.id, message=f"Edge {e.id}: source node '{from_node_id}' does not exist"))
            continue
        if not to_node:
            diags.append(Diag(code="NODE_MISSING", edgeId=e.id, message=f"Edge {e.id}: target node '{to_node_id}' does not exist"))
            continue

        op = get_port(from_node, e.from_port.port, "outputs")
        ip = get_port(to_node, e.to_port.port, "inputs")

        if not op:
            avail_outs = ", ".join(p.name for p in from_node.outputs) or "none"
            diags.append(Diag(
                code="PORT_MISSING",
                edgeId=e.id,
                nodeId=from_node.id,
                message=f"Edge {e.id}: '{from_node.id}' has no output '{e.from_port.port}'. Available outputs: {avail_outs}",
            ))
            continue
        if not ip:
            avail_ins = ", ".join(p.name for p in to_node.inputs) or "none"
            diags.append(Diag(
                code="PORT_MISSING",
                edgeId=e.id,
                nodeId=to_node.id,
                message=f"Edge {e.id}: '{to_node.id}' has no input '{e.to_port.port}'. Available inputs: {avail_ins}",
            ))
            continue

        if not type_compatible(op.type, ip.type):
            diags.append(Diag(
                code="TYPE_MISMATCH",
                edgeId=e.id,
                message=f"Edge {e.id}: {from_node.id}.{op.name}:{op.type} -> {to_node.id}.{ip.name}:{ip.type} incompatible",
            ))

        k = f"{to_node.id}.{ip.name}"
        in_count[k] = in_count.get(k, 0) + 1

    # Fan-in rule
    for k, c in in_count.items():
        if c > 1:
            diags.append(Diag(code="FAN_IN", message=f"Input {k} has {c} incoming edges (max 1 permitted)"))

    # Required inputs connected
    for n in g.nodes.values():
        for p in n.inputs:
            if p.required and f"{n.id}.{p.name}" not in in_count:
                diags.append(Diag(
                    code="UNCONNECTED_INPUT",
                    nodeId=n.id,
                    message=f"Required input {n.id}.{p.name} has no incoming edge",
                ))

    # Cycle detection via DFS
    adj: Dict[str, List[str]] = {}
    for e in g.edges:
        adj.setdefault(e.from_port.node, []).append(e.to_port.node)

    state: Dict[str, int] = {}  # 1 = visiting, 2 = visited

    def dfs(u: str, path: List[str]) -> Optional[List[str]]:
        state[u] = 1
        for v in adj.get(u, []):
            if state.get(v) == 1:
                return path + [u, v]
            if v not in state:
                r = dfs(v, path + [u])
                if r:
                    return r
        state[u] = 2
        return None

    for node_id in g.nodes.keys():
        if node_id not in state:
            cycle = dfs(node_id, [])
            if cycle:
                diags.append(Diag(code="CYCLE", message=f"Cycle detected: {' -> '.join(cycle)}"))
                break

    # AST & Code parse checks
    if parse_check:
        for n in g.nodes.values():
            err = parse_check(n)
            if err:
                diags.append(Diag(code="PARSE_ERROR", nodeId=n.id, message=f"Node {n.id} code error: {err}"))

    # Relative import resolution check for JS/TS/JSX nodes
    for n in g.nodes.values():
        lang = (n.language or "").lower()
        if lang in ("js", "jsx", "ts", "tsx"):
            for imp_match in re.finditer(r"""(?:import|from)\s+['"](\.[^'"]+)['"]""", n.code or ""):
                rel_spec = imp_match.group(1)
                if re.search(r"\.(css|scss|svg|png|jpg|jpeg|gif|webp|ico)$", rel_spec, re.I):
                    continue
                caller_dir = PurePosixPath(n.id).parent
                parts = list(caller_dir.parts)
                for segment in PurePosixPath(rel_spec).parts:
                    if segment == ".":
                        continue
                    elif segment == "..":
                        if parts:
                            parts.pop()
                    else:
                        parts.append(segment)
                resolved_stem = "/".join(parts)
                matched = any(
                    nid == resolved_stem or
                    nid.startswith(f"{resolved_stem}.") or
                    PurePosixPath(nid).with_suffix("").as_posix() == PurePosixPath(resolved_stem).with_suffix("").as_posix()
                    for nid in g.nodes
                )
                if not matched:
                    diags.append(Diag(
                        code="UNRESOLVED_IMPORT",
                        nodeId=n.id,
                        message=f"Failed to resolve import '{rel_spec}' from '{n.id}'. Target node does not exist in graph."
                    ))

    return diags


# ================= 3. IMPACT SET =================

def impact_set(g: Graph, changed: List[str], depth: int = 1) -> Dict[str, Any]:
    """BFS over neighbors up to configurable depth."""
    ids: Set[str] = set(changed)
    frontier: Set[str] = set(changed)

    for _ in range(depth):
        nxt: Set[str] = set()
        for e in g.edges:
            src = e.from_port.node
            dst = e.to_port.node
            if src in frontier and dst not in ids:
                nxt.add(dst)
            if dst in frontier and src not in ids:
                nxt.add(src)
        ids.update(nxt)
        frontier = nxt

    nodes = [g.nodes[nid] for nid in ids if nid in g.nodes]
    edges = [e for e in g.edges if e.from_port.node in ids or e.to_port.node in ids]
    neighbors = [n for n in nodes if n.id not in changed]

    return {
        "changed": changed,
        "neighbors": neighbors,
        "all_nodes": nodes,
        "all_edges": edges,
    }


# ================= 4. APPLY OPS & TRANSACTIONAL ROLLBACK =================

def apply_ops(g: Graph, ops: List[Dict[str, Any]]) -> Graph:
    """Clones graph and applies atomic operations."""
    new_nodes = {k: copy.deepcopy(v) for k, v in g.nodes.items()}
    new_edges = [copy.deepcopy(e) for e in g.edges]
    t = Graph(nodes=new_nodes, edges=new_edges)

    for o in ops:
        op_type = o.get("op")
        if op_type in ("add_node", "update_node"):
            node_data = o["node"]
            node_obj = CNode(**node_data)
            t.nodes[node_obj.id] = node_obj
        elif op_type == "remove_node":
            del_id = o["id"]
            t.nodes.pop(del_id, None)
            t.edges = [e for e in t.edges if e.from_port.node != del_id and e.to_port.node != del_id]
        elif op_type == "add_edge":
            e_id = o.get("id") or f"{o['from']['node']}.{o['from']['port']}->{o['to']['node']}.{o['to']['port']}"
            t.edges.append(CEdge(
                id=e_id,
                **{"from": PortRef(**o["from"]), "to": PortRef(**o["to"])},
            ))
        elif op_type == "remove_edge":
            del_edge_id = o["id"]
            t.edges = [e for e in t.edges if e.id != del_edge_id]

    return t


def get_touched_nodes(ops: List[Dict[str, Any]]) -> List[str]:
    touched: Set[str] = set()
    for o in ops:
        op_type = o.get("op")
        if op_type in ("add_node", "update_node"):
            touched.add(o["node"]["id"])
        elif op_type == "remove_node":
            touched.add(o["id"])
        elif op_type == "add_edge":
            touched.add(o["from"]["node"])
            touched.add(o["to"]["node"])
    return list(touched)


def build_engine_prompt(task: str, node_index: str, feedback: str = "", neighbor_context: str = "") -> str:
    """Strict prompt forcing structured operations, typed port adherence, and reviewed list."""
    prompt = (
        "You edit an architectural code graph. You do NOT decide what is valid; a deterministic compiler validator does.\n\n"
        "RULES:\n"
        "1. Output ONLY JSON: {\"ops\": [...], \"reviewed\": [...]}. No prose.\n"
        "2. Ops: add_node, update_node, remove_node, add_edge, remove_edge.\n"
        "3. Connect ONLY existing ports with matching types. Use exact node ids and port names from the index.\n"
        "4. If you change a node's inputs/outputs or code, you MUST update_node every connected neighbor or fix affected edges.\n"
        "5. 'reviewed' must list EVERY node you changed or that is connected to one you changed: action 'updated' or 'no_change' + reason.\n"
        "6. Every required input must end up connected. No cycles. Exactly one incoming edge per input port.\n\n"
        f"NODE INDEX:\n{node_index}\n\n"
    )
    if neighbor_context:
        prompt += f"IMPACTED NEIGHBOR CODE & INTERFACES:\n{neighbor_context}\n\n"
    prompt += f"TASK:\n{task}\n"
    if feedback:
        prompt += f"\nPREVIOUS ATTEMPT FAILED VALIDATION. Fix exactly these diagnostics:\n{feedback}\n"
    return prompt


async def run_engine_task(
    task: str,
    graph: Graph,
    llm_callable: Callable[[str], Any],
    max_tries: int = 3,
    type_compatible: Callable[[str, str], bool] = default_type_compatible,
    parse_check: Callable[[CNode], Optional[str]] = default_parse_check,
) -> Tuple[bool, Graph, List[Diag]]:
    """Runs two-pass bounded proposal loop with retry and transactional rollback."""
    feedback = ""
    candidate = graph
    diags: List[Diag] = []

    for attempt in range(max_tries):
        # 1. Build compact node index
        node_index_lines = []
        for n in graph.nodes.values():
            in_str = ", ".join(f"{p.name}:{p.type}" for p in n.inputs) or "none"
            out_str = ", ".join(f"{p.name}:{p.type}" for p in n.outputs) or "none"
            node_index_lines.append(f"{n.id}: {n.name} (inputs: [{in_str}], outputs: [{out_str}])")
        node_index = "\n".join(node_index_lines)

        # 2. Call LLM
        prompt = build_engine_prompt(task, node_index, feedback=feedback)
        raw_res = await llm_callable(prompt)

        # 3. Parse JSON Proposal
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_res.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            proposal = Proposal(**data)
        except Exception as e:
            feedback = f"Output was not valid JSON conforming to Proposal schema: {e}"
            logger.warning("Attempt %d failed JSON parsing: %s", attempt + 1, e)
            continue

        # 4. Apply operations to candidate clone
        try:
            candidate = apply_ops(graph, proposal.ops)
        except Exception as e:
            feedback = f"Failed to apply operations: {e}"
            continue

        # 5. Deterministic validation
        diags = validate_graph(candidate, type_compatible=type_compatible, parse_check=parse_check)

        # 6. Check that every impacted neighbor was reviewed
        touched = get_touched_nodes(proposal.ops)
        imp = impact_set(candidate, touched, depth=1)
        reviewed_set = {r.nodeId for r in proposal.reviewed}

        for neighbor in imp["neighbors"]:
            if neighbor.id not in reviewed_set:
                diags.append(Diag(
                    code="NEIGHBOR_NOT_REVIEWED",
                    nodeId=neighbor.id,
                    message=f"Impacted neighbor '{neighbor.id}' is not in 'reviewed'. You must update it or mark 'no_change' with an explicit reason.",
                ))

        # 7. Commit or retry
        if not diags:
            logger.info("Task successfully validated on attempt %d! Committing.", attempt + 1)
            return True, candidate, []

        feedback = "\n".join(f"[{d.code}] {d.message}" for d in diags)
        logger.info("Attempt %d validation failed (%d diagnostics). Retrying with feedback.", attempt + 1, len(diags))

    # Rollback: original graph untouched
    logger.warning("All %d attempts failed validation. Rolling back graph cleanly.", max_tries)
    return False, graph, diags


# ================= 5. TWO-PASS ENGINE & READ-ONLY TOOLS =================

TOOL_SCHEMAS = [
    {
        "name": "list_nodes",
        "description": "List nodes as compact signatures (id, name, input/output ports). Optional substring filter on name/id.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "get_node",
        "description": "Get one node's full source code, ports, and its incoming/outgoing edges.",
        "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    },
    {
        "name": "find_compatible_nodes",
        "description": "Find nodes that can legally connect to a port type. direction='produces': nodes with an OUTPUT assignable to the type. direction='consumes': nodes with an INPUT that accepts the type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "port_type": {"type": "string"},
                "direction": {"enum": ["produces", "consumes"]},
            },
            "required": ["port_type", "direction"],
        },
    },
]


def make_tool_executor(g: Graph, type_compatible: Callable[[str, str], bool] = default_type_compatible):
    """Creates a read-only tool executor against the committed graph."""
    def exec_tool(name: str, args: Dict[str, Any]) -> Any:
        if name == "list_nodes":
            q = (args.get("query") or "").lower()
            res = []
            for n in g.nodes.values():
                if not q or q in n.id.lower() or q in n.name.lower():
                    res.append({
                        "id": n.id,
                        "name": n.name,
                        "inputs": [f"{p.name}:{p.type}" for p in n.inputs],
                        "outputs": [f"{p.name}:{p.type}" for p in n.outputs],
                    })
            return res[:200]
        elif name == "get_node":
            node_id = args.get("id")
            n = g.nodes.get(node_id)
            if not n:
                return {"error": f"No node '{node_id}'. Use list_nodes."}
            edges = [e.dict() for e in g.edges if e.from_port.node == node_id or e.to_port.node == node_id]
            node_dict = n.dict()
            node_dict["edges"] = edges
            return node_dict
        elif name == "find_compatible_nodes":
            port_type = args.get("port_type", "")
            direction = args.get("direction", "produces")
            out = []
            for n in g.nodes.values():
                ports = (
                    [p for p in n.outputs if type_compatible(p.type, port_type)]
                    if direction == "produces"
                    else [p for p in n.inputs if type_compatible(port_type, p.type)]
                )
                if ports:
                    out.append({
                        "id": n.id,
                        "name": n.name,
                        "ports": [f"{p.name}:{p.type}" for p in ports],
                    })
            return out[:50]
        return {"error": f"Unknown tool '{name}'"}
    return exec_tool


INLINE_INDEX_LIMIT = 60


def build_scope_prompt(task: str, g: Graph) -> str:
    """Pass 1: Scope selection."""
    if len(g.nodes) <= INLINE_INDEX_LIMIT:
        lines = []
        for n in g.nodes.values():
            in_s = [f"{p.name}:{p.type}" for p in n.inputs]
            out_s = [f"{p.name}:{p.type}" for p in n.outputs]
            lines.append(json.dumps({"id": n.id, "name": n.name, "inputs": in_s, "outputs": out_s}))
        inline = "NODE INDEX:\n" + "\n".join(lines)
    else:
        inline = f"The graph has {len(g.nodes)} nodes. Use list_nodes / find_compatible_nodes to explore."

    return (
        "You are scoping a change to an architectural code graph. Do NOT write code or ops yet.\n"
        "Pick the EXISTING nodes you will edit or connect to, and describe any NEW nodes needed.\n"
        "Output ONLY JSON: {\"targets\":[{\"id\":\"...\",\"reason\":\"...\"}],\"new_nodes\":[{\"name\":\"...\",\"purpose\":\"...\"}]}\n"
        "Use only ids that exist (verify with tools). Prefer too many targets over too few.\n\n"
        f"{inline}\n\n"
        f"TASK:\n{task}"
    )


def build_pass2_ops_prompt(task: str, ctx: Dict[str, Any], new_nodes: List[Dict[str, Any]], feedback: str = "") -> str:
    """Pass 2: Ops with full injected code for in-scope nodes + neighbors."""
    code_blocks = []
    for n in ctx["all_nodes"]:
        in_s = json.dumps([p.dict() for p in n.inputs])
        out_s = json.dumps([p.dict() for p in n.outputs])
        code_blocks.append(
            f"### {n.id} ({n.name}, {n.language})\n"
            f"inputs: {in_s}\noutputs: {out_s}\n"
            f"```\n{n.code}\n```"
        )
    code_str = "\n\n".join(code_blocks)
    edges_str = json.dumps([e.dict() for e in ctx["all_edges"]])

    prompt = (
        "You edit a code graph. A deterministic validator decides validity; you only propose.\n\n"
        "RULES:\n"
        "1. Output ONLY JSON: {\"ops\":[...],\"reviewed\":[...]}. No prose.\n"
        "2. Ops: add_node, update_node, remove_node, add_edge, remove_edge.\n"
        "3. Only update_node / remove_node for nodes shown in CONTEXT. If you need another node, call get_node first.\n"
        "4. Connect ONLY existing ports with matching types. Use exact ids and port names.\n"
        "5. If you change a node's ports, update_node every connected neighbor and fix/remove affected edges.\n"
        "6. 'reviewed' must list every node you changed AND every neighbor of a changed node: {nodeId, action:\"updated\"|\"no_change\", reason}.\n"
        "7. Required inputs must be connected. No cycles. One incoming edge per input port.\n\n"
        f"CONTEXT: nodes (full code)\n{code_str}\n\n"
        f"CONTEXT: edges\n{edges_str}\n\n"
        f"PLANNED NEW NODES:\n{json.dumps(new_nodes)}\n\n"
        f"TASK:\n{task}\n"
    )
    if feedback:
        prompt += f"\nPREVIOUS ATTEMPT FAILED. Fix exactly these:\n{feedback}\n"
    return prompt


async def run_two_pass(
    task: str,
    graph: Graph,
    tool_llm: Callable[[str, List[Dict[str, Any]], Callable[[str, Dict[str, Any]], Any]], Any],
    type_compatible: Callable[[str, str], bool] = default_type_compatible,
    parse_check: Callable[[CNode], Optional[str]] = default_parse_check,
    max_tries: int = 3,
) -> Tuple[bool, Graph, List[Diag]]:
    """Two-Pass Graph Engine:
    - Pass 1: Compact Index/Tool Scoping -> target nodes.
    - Pass 2: Injects full code of targets + 1-hop impactSet.
    - Validation checks OUT_OF_SCOPE_EDIT, NEIGHBOR_NOT_REVIEWED, and structural rules.
    - Dynamic scope expansion on retry.
    - Atomic rollback on failure.
    """
    exec_tool = make_tool_executor(graph, type_compatible=type_compatible)

    # Pass 1: Scoping
    p1_prompt = build_scope_prompt(task, graph)
    raw_scope = await tool_llm(p1_prompt, TOOL_SCHEMAS, exec_tool)

    targets: Set[str] = set()
    new_nodes_plan: List[Dict[str, Any]] = []
    try:
        cleaned_scope = re.sub(r"^```(?:json)?\s*", "", raw_scope.strip())
        cleaned_scope = re.sub(r"\s*```$", "", cleaned_scope)
        scope_data = json.loads(cleaned_scope)
        for t in scope_data.get("targets", []):
            tid = t.get("id")
            if tid and tid in graph.nodes:
                targets.add(tid)
        new_nodes_plan = scope_data.get("new_nodes", [])
    except Exception as e:
        logger.warning("Pass 1 scoping parse error (%s); falling back to empty scope.", e)

    feedback = ""
    diags: List[Diag] = []
    candidate = graph

    for attempt in range(max_tries):
        # 1. Compute impact set for all in-scope targets
        ctx = impact_set(graph, list(targets), depth=1)
        in_scope = {n.id for n in ctx["all_nodes"]}

        # 2. Pass 2 prompt with full code
        p2_prompt = build_pass2_ops_prompt(task, ctx, new_nodes_plan, feedback=feedback)
        raw_ops = await tool_llm(p2_prompt, TOOL_SCHEMAS, exec_tool)

        # 3. Parse Proposal
        try:
            cleaned_ops = re.sub(r"^```(?:json)?\s*", "", raw_ops.strip())
            cleaned_ops = re.sub(r"\s*```$", "", cleaned_ops)
            prop_data = json.loads(cleaned_ops)
            proposal = Proposal(**prop_data)
        except Exception as e:
            feedback = f"Output was not valid JSON per schema: {e}"
            continue

        # 4. Apply operations
        try:
            candidate = apply_ops(graph, proposal.ops)
        except Exception as e:
            feedback = f"Failed to apply operations: {e}"
            continue

        # 5. Validate graph
        diags = validate_graph(candidate, type_compatible=type_compatible, parse_check=parse_check)

        # 6. Check OUT_OF_SCOPE_EDIT
        for o in proposal.ops:
            op_type = o.get("op")
            if op_type in ("update_node", "remove_node"):
                node_id = o["node"]["id"] if op_type == "update_node" else o["id"]
                if node_id in graph.nodes and node_id not in in_scope:
                    diags.append(Diag(
                        code="OUT_OF_SCOPE_EDIT",
                        nodeId=node_id,
                        message=f"Edited '{node_id}' without its code in context. Its code is now included; redo using it.",
                    ))

        # 7. Check NEIGHBOR_NOT_REVIEWED
        touched = get_touched_nodes(proposal.ops)
        imp = impact_set(candidate, touched, depth=1)
        reviewed_set = {r.nodeId for r in proposal.reviewed}

        for neighbor in imp["neighbors"]:
            if neighbor.id not in reviewed_set:
                diags.append(Diag(
                    code="NEIGHBOR_NOT_REVIEWED",
                    nodeId=neighbor.id,
                    message=f"Impacted neighbor '{neighbor.id}' not in 'reviewed'. Update it or mark no_change with a reason.",
                ))

        # 8. Success commit
        if not diags:
            logger.info("Two-pass task passed validation on attempt %d! Committing.", attempt + 1)
            return True, candidate, []

        # 9. Dynamic scope expansion: expand targets with touched & flagged nodes
        for tid in touched:
            if tid in graph.nodes:
                targets.add(tid)
        for d in diags:
            if d.nodeId and d.nodeId in graph.nodes:
                targets.add(d.nodeId)

        feedback = "\n".join(f"[{d.code}] {d.message}" for d in diags)
        logger.info("Attempt %d failed with %d diagnostics. Scope expanded to %d nodes. Retrying.", attempt + 1, len(diags), len(targets))

    # Rollback untouched
    return False, graph, diags
