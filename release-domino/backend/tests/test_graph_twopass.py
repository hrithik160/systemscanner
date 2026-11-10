"""Unit tests for the Two-Pass Graph Engine, Tool Executor, and Deterministic Validator."""
import pytest
from app.llm.graph_engine import (
    Graph,
    CNode,
    Port,
    CEdge,
    PortRef,
    validate_graph,
    impact_set,
    make_tool_executor,
    run_two_pass,
)


@pytest.fixture
def sample_graph() -> Graph:
    """Fixture providing a multi-stack graph: Frontend App -> Auth Service -> Database."""
    return Graph(
        nodes={
            "src/App.jsx": CNode(
                id="src/App.jsx",
                name="App",
                language="jsx",
                code="export default function App() { return <div>App</div>; }",
                inputs=[Port(name="in_children", type="ReactComponent", required=False)],
                outputs=[Port(name="out_auth", type="HTTP_Client")],
            ),
            "app/auth.py": CNode(
                id="app/auth.py",
                name="AuthService",
                language="py",
                code="def login(req): return {'token': 'xyz'}",
                inputs=[Port(name="in_http", type="HTTP_Endpoint")],
                outputs=[
                    Port(name="out_db", type="DBConnection"),
                    Port(name="out_func", type="PythonCallable"),
                ],
            ),
            "app/db.py": CNode(
                id="app/db.py",
                name="Database",
                language="py",
                code="def query(): pass",
                inputs=[Port(name="in_conn", type="DBConnection")],
                outputs=[],
            ),
        },
        edges=[
            CEdge(
                id="e1",
                **{"from": PortRef(node="app/auth.py", port="out_db"), "to": PortRef(node="app/db.py", port="in_conn")},
            )
        ],
    )


def test_type_mismatch_diagnostic(sample_graph: Graph):
    """Directly connecting PythonCallable to ReactComponent must fail with TYPE_MISMATCH."""
    sample_graph.edges.append(
        CEdge(
            id="e_broken_type",
            **{"from": PortRef(node="app/auth.py", port="out_func"), "to": PortRef(node="src/App.jsx", port="in_children")},
        )
    )
    diags = validate_graph(sample_graph)
    codes = [d.code for d in diags]
    assert "TYPE_MISMATCH" in codes
    assert any("incompatible" in d.message for d in diags)


def test_missing_port_diagnostic(sample_graph: Graph):
    """Connecting to a non-existent port must fail with PORT_MISSING."""
    sample_graph.edges.append(
        CEdge(
            id="e_broken_port",
            **{"from": PortRef(node="app/auth.py", port="out_func"), "to": PortRef(node="app/db.py", port="non_existent")},
        )
    )
    diags = validate_graph(sample_graph)
    codes = [d.code for d in diags]
    assert "PORT_MISSING" in codes
    assert any("has no input 'non_existent'" in d.message for d in diags)


def test_cycle_detection(sample_graph: Graph):
    """Creating a cycle must fail with CYCLE."""
    sample_graph.nodes["app/db.py"].outputs.append(Port(name="out_cycle", type="HTTP_Endpoint"))
    sample_graph.edges.append(
        CEdge(
            id="e_cycle",
            **{"from": PortRef(node="app/db.py", port="out_cycle"), "to": PortRef(node="app/auth.py", port="in_http")},
        )
    )
    diags = validate_graph(sample_graph)
    codes = [d.code for d in diags]
    assert "CYCLE" in codes
    assert any("Cycle detected" in d.message for d in diags)


def test_tool_executor_read_only(sample_graph: Graph):
    """Tools must execute queries against the committed graph."""
    exec_tool = make_tool_executor(sample_graph)

    # 1. list_nodes
    nodes = exec_tool("list_nodes", {"query": "auth"})
    assert len(nodes) == 1
    assert nodes[0]["id"] == "app/auth.py"

    # 2. get_node
    node = exec_tool("get_node", {"id": "app/auth.py"})
    assert node["id"] == "app/auth.py"
    assert len(node["edges"]) == 1

    # 3. find_compatible_nodes
    compat = exec_tool("find_compatible_nodes", {"port_type": "DBConnection", "direction": "consumes"})
    assert any(c["id"] == "app/db.py" for c in compat)


@pytest.mark.anyio
async def test_two_pass_retry_and_neighbor_review(sample_graph: Graph):
    """Simulates LLM failing neighbor review on try 1, then succeeding on try 2 with scope expansion."""
    attempts = 0

    async def mock_tool_llm(prompt: str, tools: list, exec_fn):
        nonlocal attempts
        # Pass 1: Scope selection
        if "scoping a change" in prompt:
            return '{"targets":[{"id":"app/auth.py","reason":"Update auth logic"}],"new_nodes":[]}'

        # Pass 2: Operations proposal
        attempts += 1
        if attempts == 1:
            # Fails: forgets to review impacted neighbor 'app/db.py'
            return """{
                "ops": [
                    {
                        "op": "update_node",
                        "node": {
                            "id": "app/auth.py",
                            "name": "AuthService",
                            "language": "py",
                            "code": "def login(): pass",
                            "inputs": [{"name": "in_http", "type": "HTTP_Endpoint", "required": false}],
                            "outputs": [{"name": "out_db", "type": "DBConnection", "required": false}]
                        }
                    }
                ],
                "reviewed": [
                    {"nodeId": "app/auth.py", "action": "updated", "reason": "Added clean login handler"}
                ]
            }"""
        else:
            # Succeeds: reviews neighbor 'app/db.py' as no_change
            return """{
                "ops": [
                    {
                        "op": "update_node",
                        "node": {
                            "id": "app/auth.py",
                            "name": "AuthService",
                            "language": "py",
                            "code": "def login(): pass",
                            "inputs": [{"name": "in_http", "type": "HTTP_Endpoint", "required": false}],
                            "outputs": [{"name": "out_db", "type": "DBConnection", "required": false}]
                        }
                    }
                ],
                "reviewed": [
                    {"nodeId": "app/auth.py", "action": "updated", "reason": "Added clean login handler"},
                    {"nodeId": "app/db.py", "action": "no_change", "reason": "DB contract intact and requires no change"}
                ]
            }"""

    ok, candidate, diags = await run_two_pass("Add clean login handler", sample_graph, mock_tool_llm, max_tries=3)
    assert ok is True
    assert len(diags) == 0
    assert attempts == 2
    assert "def login(): pass" in candidate.nodes["app/auth.py"].code


def test_unresolved_import_and_strictnode_diagnostic(sample_graph: Graph):
    """Proves that importing non-existent modules or hallucinating StrictNode fires diagnostics immediately."""
    # 1. Hallucinated StrictNode must fire PARSE_ERROR
    sample_graph.nodes["src/App.jsx"].code = "import { StrictNode } from 'react'; export default function App() {}"
    diags = validate_graph(sample_graph)
    codes = [d.code for d in diags]
    assert "PARSE_ERROR" in codes
    assert any("StrictNode" in d.message for d in diags)

    # 2. Unresolved import './homepage' must fire UNRESOLVED_IMPORT
    sample_graph.nodes["src/App.jsx"].code = "import { homepage } from './homepage'; export default function App() {}"
    diags = validate_graph(sample_graph)
    codes = [d.code for d in diags]
    assert "UNRESOLVED_IMPORT" in codes
    assert any("homepage" in d.message for d in diags)

