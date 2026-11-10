// Shared contracts between Person 1, Person 2, Person 3, and Person 4 (Section 5 of Release Domino Team Guide)
// Direction rule: an edge source -> target means source depends on (imports) target.
// A change in a node impacts the nodes that depend on it, so impact travels along edges in reverse.

export type NodeKind = 'module' | 'route' | 'service' | 'view' | 'infra' | 'sandbox';
export type NodeLang = 'py' | 'ts' | 'tsx' | 'js' | 'jsx' | 'other';
export type NodeStatus = 'normal' | 'changed' | 'impacted' | 'failing';
export type EdgeType = 'import' | 'call' | 'http' | 'infra';
export type Verdict = 'GO' | 'CAUTION' | 'HOLD';

export interface CNode {
  id: string;
  label: string;
  path: string;
  kind: NodeKind;
  lang: NodeLang;
  loc: number;
  churn: { added: number; deleted: number }; // vs base (HEAD or origin/main)
  defect_score: number; // 0-10, from git history
  coverage: number | null; // 0-1, null if unknown
  coverage_estimated: boolean;
  is_crown_jewel: boolean;
  status: NodeStatus;
  risk: number; // 0-100 per node
  exports: string[];
  group?: string; // folder group for collapse when >300 nodes
  pos?: { x: number; y: number };
  depth?: number; // BFS blast-radius depth when impacted
  impact?: number; // 0-1 impact score from BFS decay
}

export interface CEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  weight: number; // 0-1
  active_shockwave?: boolean;
  depth?: number;
}

export interface Graph {
  project_id: string;
  nodes: CNode[];
  edges: CEdge[];
}

export interface DiffFileHunk {
  start: number;
  end: number;
}

export interface DiffFileEntry {
  path: string;
  added: number;
  deleted: number;
  hunks: DiffFileHunk[];
}

export interface DiffResult {
  files: DiffFileEntry[];
  total_added: number;
  total_deleted: number;
}

export interface MergeConflictEntry {
  path: string;
  lines: [number, number][];
}

export interface MergeResult {
  clean: boolean;
  base: string;
  conflicts: MergeConflictEntry[];
}

export interface TestFailureItem {
  test: string;
  node_id: string | null;
  message: string;
}

export interface TestRunResult {
  run_id: string;
  passed: number;
  failed: number;
  errors: number;
  duration_s: number;
  coverage: Record<string, number>;
  failures: TestFailureItem[];
  selected_tests?: number;
  total_tests?: number;
  output?: string;
}

export interface RiskFactor {
  name: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface ImpactedNodeEntry {
  id: string;
  impact: number;
  depth: number;
}

export interface RiskResult {
  score: number;
  verdict: Verdict;
  factors: RiskFactor[];
  changed_nodes: string[];
  impacted: ImpactedNodeEntry[];
  reasons: string[];
  coverage_estimated: boolean;
  computed_at: number;
  baseline_score?: number;
  baseline_verdict?: Verdict;
  test_penalty?: number;
  merge_penalty?: number;
}

export type WSEventType =
  | 'graph_loaded'
  | 'node_updated'
  | 'summary_ready'
  | 'diff_updated'
  | 'merge_checked'
  | 'coverage_updated'
  | 'test_run_finished'
  | 'impact_computed'
  | 'risk_updated'
  | 'file_changed'
  | 'node_pulse'
  | 'active_nodes'
  | 'error';

export interface WSEventEnvelope<T = unknown> {
  type: WSEventType;
  project_id: string;
  payload: T;
  ts: number;
}

export interface NodeSummaryData {
  summary: string[];
  purpose: string;
  risks: string[];
  exports: string[];
}

export interface NodeDetailResponse {
  id: string;
  label: string;
  path: string;
  kind: NodeKind;
  lang: NodeLang;
  loc: number;
  code: string;
  exports: string[];
  dependencies: string[];
  dependents: string[];
  churn: { added: number; deleted: number };
  defect_score: number;
  defect_history: { commits_180d: number; fixes_180d: number; reverts_180d: number; recent_messages: string[] };
  coverage: number | null;
  coverage_estimated: boolean;
  is_crown_jewel: boolean;
  status: NodeStatus;
  risk: number;
  cached_summary: NodeSummaryData | null;
}

export interface ArchitectureData {
  stack: string[];
  infra: string[];
  node_infra_links: { node_id: string; infra: string }[];
  summary: string;
}

export interface SandboxConnectProposal {
  proposal_id: string;
  patch: string;
  endpoint: string;
  rationale: string;
  source_node_id?: string;
  target_node_id?: string;
}

export interface CompareNodeDelta {
  id: string;
  label: string;
  path: string;
  kind: NodeKind;
  base_risk: number;
  head_risk: number;
  delta: number;
  churn_added: number;
  churn_deleted: number;
  status: NodeStatus;
}

export interface ReleaseComparisonResult {
  project_id: string;
  base_ref: string;
  head_ref: string;
  base_score: number;
  head_score: number;
  base_verdict: Verdict;
  head_verdict: Verdict;
  deltas: CompareNodeDelta[];
}
