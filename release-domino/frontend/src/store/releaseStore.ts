import { create } from 'zustand';
import {
  ArchitectureData,
  CEdge,
  CNode,
  DiffResult,
  Graph,
  MergeResult,
  NodeDetailResponse,
  NodeLang,
  NodeSummaryData,
  ReleaseComparisonResult,
  RiskResult,
  SandboxConnectProposal,
  TestRunResult,
  WSEventEnvelope,
} from '../../../shared/types';
import mockGraphJson from '../../../shared/mock/graph.json';
import mockRiskJson from '../../../shared/mock/risk.json';

export type WorkspaceMode = 'live' | 'whatif';
export type InspectorTab = 'xray' | 'risk' | 'arch' | 'wire';

const INITIAL_MOCK_GRAPH = mockGraphJson as unknown as Graph;
const INITIAL_MOCK_RISK = mockRiskJson as unknown as RiskResult;

const INITIAL_DIFF: DiffResult = {
  total_added: 66,
  total_deleted: 19,
  files: [
    { path: 'app/auth.py', added: 48, deleted: 12, hunks: [{ start: 18, end: 66 }] },
    { path: 'app/checkout.py', added: 14, deleted: 6, hunks: [{ start: 42, end: 62 }] },
    { path: 'app/main.py', added: 4, deleted: 1, hunks: [{ start: 10, end: 15 }] },
  ],
};

const INITIAL_MERGE: MergeResult = {
  clean: false,
  base: 'origin/main',
  conflicts: [{ path: 'app/auth.py', lines: [[1, 9]] }],
};

const INITIAL_ARCH: ArchitectureData = {
  stack: ['Python 3.12', 'FastAPI', 'Redis', 'PostgreSQL', 'Pytest', 'Docker Sandbox'],
  infra: ['Redis Session & Rate-Limit Store', 'PostgreSQL Primary Database'],
  node_infra_links: [
    { node_id: 'app/redis_cache.py', infra: 'Redis' },
    { node_id: 'app/auth.py', infra: 'Redis' },
    { node_id: 'app/db.py', infra: 'PostgreSQL' },
    { node_id: 'app/orders_route.py', infra: 'PostgreSQL' },
  ],
  summary:
    'FastAPI e-commerce microservice architecture backed by Redis for session/rate-limit caching and PostgreSQL for transactional order persistence. Authentication (app/auth.py) and Checkout (app/checkout.py) act as high-gravity Crown Jewel services.',
};

export interface RegisteredProjectItem {
  project_id: string;
  name: string;
  path: string;
  runtime?: string;
}

export interface NodeChangeProposal {
  node_id: string;
  direction: 'input' | 'output';
  original_code: string;
  modified_code: string;
  patch: string;
  endpoint: string;
  rationale: string;
}

export interface ClarificationOption {
  id: string;
  title: string;
  description: string;
  is_recommended?: boolean;
  patch_action?: any;
}

export interface ClarificationQuestion {
  id: string;
  severity: 'critical' | 'warning' | 'suggestion';
  title: string;
  question: string;
  reason: string;
  options: ClarificationOption[];
}

export interface BatchWirePreviewResult {
  preview_id: string;
  new_node: {
    name: string;
    code: string;
    lang: 'py' | 'ts' | 'tsx' | 'js' | 'jsx' | string;
    is_crown_jewel: boolean;
  };
  connected_changes: NodeChangeProposal[];
  clarification_questions?: ClarificationQuestion[];
}

export interface ReleaseStoreState {
  projectId: string;
  projects: RegisteredProjectItem[];
  useMockMode: boolean;
  mode: WorkspaceMode;
  connected: boolean;
  isLoadingProject: boolean;
  errorBanner: string | null;

  graph: Graph;
  risk: RiskResult;
  diff: DiffResult;
  merge: MergeResult;
  lastTestRun: TestRunResult | null;
  architecture: ArchitectureData;
  comparison: ReleaseComparisonResult | null;

  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  nodeDetail: NodeDetailResponse | null;
  isSummarizing: boolean;
  activeInspectorTab: InspectorTab;
  collapseFolders: boolean;

  shockwaveStep: number | null;
  isShockwavePlaying: boolean;
  shockwaveSpeed: number;
  dockerAutoRunCounter: number;

  viewMode: '2d' | '3d';
  setViewMode: (mode: '2d' | '3d') => void;
  toggleViewMode: () => void;

  isNodeStudioOpen: boolean;
  setIsNodeStudioOpen: (open: boolean) => void;
  isOpenProjectModalOpen: boolean;
  isSandboxNodeModalOpen: boolean;
  isScorecardModalOpen: boolean;
  isTerminalOpen: boolean;
  pendingConnectProposal: SandboxConnectProposal | null;
  isConnectingNodes: boolean;
  isBatchWiring: boolean;
  batchWirePreview: BatchWirePreviewResult | null;
  setBatchWirePreview: (preview: BatchWirePreviewResult | null) => void;

  isRunningTests: boolean;
  isGeneratingTests: boolean;
  generatedTestCode: string;
  agentPrompt: string;
  isRunningAgent: boolean;
  agentResult: any | null;
  antiPatternResult: any | null;
  conflictResolutionResult: any | null;
  autoHealResult: any | null;

  wireLogs: string[];
  dockerStatus: { docker_available: boolean; images: Record<string, boolean>; active_containers: string[] } | null;
  llmStatus: {
    ollama_online: boolean;
    configured_model: string;
    fallback_ready: boolean;
    provider?: string;
    provider_name?: string;
    nvidia_configured?: boolean;
    deepseek_configured?: boolean;
    ollama_url?: string;
    model_id?: string;
    endpoint_url?: string;
    available_models?: string[];
    fallback_provider?: string;
    masked_key?: string;
    is_online?: boolean;
  } | null;
  isAiInspectorOpen: boolean;
  setIsAiInspectorOpen: (open: boolean) => void;

  setConnected: (connected: boolean) => void;
  setUseMockMode: (useMock: boolean) => void;
  setMode: (mode: WorkspaceMode) => void;
  setErrorBanner: (msg: string | null) => void;
  setActiveInspectorTab: (tab: InspectorTab) => void;
  setCollapseFolders: (collapse: boolean) => void;
  setIsOpenProjectModalOpen: (open: boolean) => void;
  setIsSandboxNodeModalOpen: (open: boolean) => void;
  setIsScorecardModalOpen: (open: boolean) => void;
  setIsTerminalOpen: (open: boolean) => void;
  setPendingConnectProposal: (prop: SandboxConnectProposal | null) => void;
  setGeneratedTestCode: (code: string) => void;
  setAgentPrompt: (prompt: string) => void;
  appendWireLog: (raw: string) => void;
  clearWireLogs: () => void;

  fetchInitialWorkspace: (pid?: string) => Promise<void>;
  openProject: (source: 'local' | 'github', pathOrUrl: string, branch?: string) => Promise<boolean>;
  uploadProjectFolder: (projectName: string, files: { path: string; content: string; is_base64: boolean }[]) => Promise<boolean>;
  selectNode: (nodeId: string | null) => Promise<void>;
  selectEdge: (edgeId: string | null) => void;
  updateNodePosition: (nodeId: string, pos: { x: number; y: number }) => void;
  summarizeSelectedNode: (nodeId?: string) => Promise<void>;
  chatWithFileNode: (nodeId: string, prompt: string, code?: string, history?: { role: string; content: string }[]) => Promise<{ reply: string; suggested_code?: string | null }>;
  saveNodeCode: (nodeId: string, newCode: string) => Promise<void>;
  toggleCrownJewel: (nodeId: string) => Promise<void>;
  createSandboxNode: (name: string, code: string, lang: 'py' | 'ts' | 'tsx' | 'js' | 'jsx' | string, isCrown: boolean) => Promise<void>;
  aiGenerateNode: (prompt: string, lang?: string) => Promise<{
    name: string;
    code: string;
    lang: 'py' | 'ts' | 'tsx' | 'js' | 'jsx' | string;
    is_crown_jewel: boolean;
    suggested_inputs: string[];
    suggested_outputs: string[];
    explanation: string;
  }>;
  previewBatchWire: (params: {
    new_node_name: string;
    new_node_code: string;
    new_node_lang: 'py' | 'ts' | 'tsx' | 'js' | 'jsx' | string;
    is_crown_jewel: boolean;
    input_node_ids: string[];
    output_node_ids: string[];
  }) => Promise<BatchWirePreviewResult | null>;
  finalizeBatchWire: (previewId: string, apply: boolean, payload?: any) => Promise<boolean>;
  proposeEdgeConnection: (sourceId: string, targetId: string) => Promise<void>;
  applyEdgeConnection: (proposalId: string) => Promise<void>;
  severEdge: (edgeId: string) => Promise<void>;
  runTests: (onlyImpacted?: boolean, customTestCode?: string) => Promise<void>;
  triggerDockerRunWithShockwave: () => void;
  generateTestsForNode: (nodeId: string) => Promise<void>;
  runAgentLoop: (promptText?: string) => Promise<void>;
  runAntiPatternScan: (nodeId: string) => Promise<void>;
  runConflictResolver: (filePath?: string) => Promise<void>;
  runAutoHeal: () => Promise<void>;
  fetchComparison: (base?: string, head?: string) => Promise<void>;
  testLlmConnection: () => Promise<any>;
  updateLlmConfig: (apiKey: string, model?: string) => Promise<boolean>;

  startShockwave: (speed?: number) => void;
  pauseShockwave: () => void;
  resetShockwave: () => void;
  setShockwaveStep: (step: number | null) => void;

  isProgramRunning: boolean;
  executingNodeIds: string[];
  activeFlowEdgeIds: string[];
  startExecutionTrace: (initialNodeId?: string) => void;
  setExecutingNode: (nodeIdOrPath: string) => void;
  stopExecutionTrace: () => void;

  applyWsEvent: (envelope: WSEventEnvelope) => void;
}

let shockwaveTimer: ReturnType<typeof setInterval> | null = null;

export const useReleaseStore = create<ReleaseStoreState>((set, get) => ({
  projectId: 'demo',
  projects: [{ project_id: 'demo', name: 'demo_shop_repo (FastAPI + Redis)', path: 'demo/demo_shop_repo', runtime: 'py' }],
  useMockMode: (import.meta as any).env?.VITE_USE_MOCK === '1',
  mode: 'live',
  connected: false,
  isLoadingProject: false,
  errorBanner: null,

  graph: structuredClone(INITIAL_MOCK_GRAPH),
  risk: structuredClone(INITIAL_MOCK_RISK),
  diff: structuredClone(INITIAL_DIFF),
  merge: structuredClone(INITIAL_MERGE),
  lastTestRun: null,
  architecture: structuredClone(INITIAL_ARCH),
  comparison: null,

  selectedNodeId: 'app/auth.py',
  selectedEdgeId: null,
  nodeDetail: null,
  isSummarizing: false,
  activeInspectorTab: 'xray',
  collapseFolders: false,

  shockwaveStep: null,
  isShockwavePlaying: false,
  shockwaveSpeed: 1,
  dockerAutoRunCounter: 0,

  isProgramRunning: false,
  executingNodeIds: [],
  activeFlowEdgeIds: [],

  viewMode: '2d',
  setViewMode: (viewMode) => set({ viewMode }),
  toggleViewMode: () => set((state) => ({ viewMode: state.viewMode === '3d' ? '2d' : '3d' })),

  isNodeStudioOpen: false,
  setIsNodeStudioOpen: (isNodeStudioOpen) => set({ isNodeStudioOpen }),
  isOpenProjectModalOpen: false,
  isSandboxNodeModalOpen: false,
  isScorecardModalOpen: false,
  isTerminalOpen: false,
  isAiInspectorOpen: false,
  setIsAiInspectorOpen: (isAiInspectorOpen) => set({ isAiInspectorOpen }),
  pendingConnectProposal: null,
  isConnectingNodes: false,
  isBatchWiring: false,
  batchWirePreview: null,
  setBatchWirePreview: (batchWirePreview) => set({ batchWirePreview }),

  isRunningTests: false,
  isGeneratingTests: false,
  generatedTestCode: '',
  agentPrompt: 'Add a Redis rate limiter to login_route and auth to block brute-force token requests',
  isRunningAgent: false,
  agentResult: null,
  antiPatternResult: null,
  conflictResolutionResult: null,
  autoHealResult: null,

  wireLogs: [],
  dockerStatus: null,
  llmStatus: null,

  setConnected: (connected) => set({ connected }),
  setUseMockMode: (useMockMode) => {
    set({ useMockMode });
    if (useMockMode) {
      set({
        graph: structuredClone(INITIAL_MOCK_GRAPH),
        risk: structuredClone(INITIAL_MOCK_RISK),
        diff: structuredClone(INITIAL_DIFF),
        merge: structuredClone(INITIAL_MERGE),
        architecture: structuredClone(INITIAL_ARCH),
      });
    } else {
      get().fetchInitialWorkspace(get().projectId);
    }
  },
  setMode: (mode) => set({ mode }),
  setErrorBanner: (errorBanner) => set({ errorBanner }),
  setActiveInspectorTab: (activeInspectorTab) => set({ activeInspectorTab }),
  setCollapseFolders: (collapseFolders) => set({ collapseFolders }),
  setIsOpenProjectModalOpen: (isOpenProjectModalOpen) => set({ isOpenProjectModalOpen }),
  setIsSandboxNodeModalOpen: (isSandboxNodeModalOpen) => set({ isSandboxNodeModalOpen }),
  setIsScorecardModalOpen: (isScorecardModalOpen) => {
    set({ isScorecardModalOpen });
    if (isScorecardModalOpen) {
      get().fetchComparison();
    }
  },
  setIsTerminalOpen: (isTerminalOpen) => set({ isTerminalOpen }),
  setPendingConnectProposal: (pendingConnectProposal) => set({ pendingConnectProposal }),
  setGeneratedTestCode: (generatedTestCode) => set({ generatedTestCode }),
  setAgentPrompt: (agentPrompt) => set({ agentPrompt }),

  appendWireLog: (raw) =>
    set((state) => ({
      wireLogs: [raw, ...state.wireLogs.slice(0, 99)],
    })),
  clearWireLogs: () => set({ wireLogs: [] }),

  fetchInitialWorkspace: async (targetPid?: string) => {
    const pid = targetPid || get().projectId;
    set({ isLoadingProject: true, errorBanner: null });

    try {
      const [projRes, dockerRes, llmRes] = await Promise.allSettled([
        fetch('/api/sandbox/projects').then((r) => (r.ok ? r.json() : null)),
        fetch('/api/docker/status').then((r) => (r.ok ? r.json() : null)),
        fetch('/api/llm/status').then((r) => (r.ok ? r.json() : null)),
      ]);

      if (projRes.status === 'fulfilled' && projRes.value?.projects) {
        const norm = projRes.value.projects.map((item: any) => ({
          ...item,
          project_id: item.project_id || item.pid || item.name,
          pid: item.project_id || item.pid || item.name,
          name: item.name || item.project_id || item.pid,
          runtime: item.runtime || item.stack || "py",
        }));
        set({ projects: norm });
      }
      if (dockerRes.status === 'fulfilled' && dockerRes.value) {
        set({ dockerStatus: dockerRes.value });
      }
      if (llmRes.status === 'fulfilled' && llmRes.value) {
        set({ llmStatus: llmRes.value });
      }

      if (get().useMockMode && pid === "demo") {
        set({ isLoadingProject: false });
        return;
      }

      const [gRes, rRes, dRes, mRes, aRes] = await Promise.allSettled([
        fetch(`/api/graph/${encodeURIComponent(pid)}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/risk/${encodeURIComponent(pid)}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/diff/${encodeURIComponent(pid)}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/merge-check/${encodeURIComponent(pid)}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/architecture/${encodeURIComponent(pid)}`).then((r) => (r.ok ? r.json() : null)),
      ]);

      const nextGraph: Graph =
        gRes.status === 'fulfilled' && gRes.value?.nodes
          ? gRes.value
          : pid === "demo"
          ? structuredClone(INITIAL_MOCK_GRAPH)
          : { project_id: pid, nodes: [], edges: [] };
      const nextRisk: RiskResult =
        rRes.status === 'fulfilled' && rRes.value && typeof rRes.value.score === 'number'
          ? rRes.value
          : structuredClone(INITIAL_MOCK_RISK);
      const nextDiff: DiffResult =
        dRes.status === 'fulfilled' && dRes.value ? dRes.value : structuredClone(INITIAL_DIFF);
      const nextMerge: MergeResult =
        mRes.status === 'fulfilled' && mRes.value ? mRes.value : structuredClone(INITIAL_MERGE);
      const nextArch: ArchitectureData =
        aRes.status === 'fulfilled' && aRes.value?.stack ? aRes.value : structuredClone(INITIAL_ARCH);

      const firstInterestingNode =
        nextGraph.nodes.find((n) => n.status === 'changed' || n.is_crown_jewel)?.id ||
        nextGraph.nodes[0]?.id ||
        null;

      set({
        projectId: pid,
        graph: nextGraph,
        risk: nextRisk,
        diff: nextDiff,
        merge: nextMerge,
        architecture: nextArch,
        collapseFolders: nextGraph.nodes.length > 300,
        isLoadingProject: false,
      });

      if (firstInterestingNode) {
        await get().selectNode(firstInterestingNode);
      }
    } catch (err: any) {
      set({
        isLoadingProject: false,
        errorBanner: `Backend unreachable — running on local mock state (${err?.message || 'offline'})`,
      });
    }
  },

  openProject: async (source, pathOrUrl, branch) => {
    set({ isLoadingProject: true, errorBanner: null });
    try {
      const resp = await fetch('/api/project/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          source === 'github'
            ? { source: 'github', url: pathOrUrl, branch }
            : { source: 'local', path: pathOrUrl }
        ),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to open project');
      }
      const newPid = data.project_id || data.pid || data.id;
      set({ isOpenProjectModalOpen: false, projectId: newPid, useMockMode: false });
      await get().fetchInitialWorkspace(newPid);
      get().startShockwave(1);
      return true;
    } catch (err: any) {
      set({ isLoadingProject: false, errorBanner: err?.message || 'Could not open project' });
      return false;
    }
  },

  uploadProjectFolder: async (projectName, files) => {
    set({ isLoadingProject: true, errorBanner: null });
    try {
      const resp = await fetch('/api/sandbox/upload-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: projectName, files }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data?.detail?.error?.message || 'Folder upload failed');
      }
      const newPid = data.project_id || data.pid || data.id;
      set({ isOpenProjectModalOpen: false, projectId: newPid, useMockMode: false });
      await get().fetchInitialWorkspace(newPid);
      return true;
    } catch (err: any) {
      set({ isLoadingProject: false, errorBanner: err?.message || 'Upload failed' });
      return false;
    }
  },

  selectNode: async (nodeId) => {
    set({ selectedNodeId: nodeId, selectedEdgeId: null, antiPatternResult: null, isNodeStudioOpen: !!nodeId });
    if (!nodeId) {
      set({ nodeDetail: null });
      return;
    }

    const { projectId, graph, useMockMode } = get();
    const gNode = graph.nodes.find((n) => n.id === nodeId);

    const fallbackDetail: NodeDetailResponse = {
      id: gNode?.id || nodeId,
      label: gNode?.label || nodeId,
      path: gNode?.path || nodeId,
      kind: gNode?.kind || 'module',
      lang: gNode?.lang || 'py',
      loc: gNode?.loc || 45,
      code: `# Source file: ${nodeId}\nimport redis_cache\n\ndef authenticate_user(username: str, token: str) -> bool:\n    """Validates JWT session token and checks Redis cache."""\n    if not token:\n        return False\n    return True\n`,
      exports: gNode?.exports || [],
      dependencies: graph.edges.filter((e) => e.source === nodeId).map((e) => e.target),
      dependents: graph.edges.filter((e) => e.target === nodeId).map((e) => e.source),
      churn: gNode?.churn || { added: 0, deleted: 0 },
      defect_score: gNode?.defect_score || 0,
      defect_history: {
        commits_180d: 8,
        fixes_180d: 4,
        reverts_180d: 1,
        recent_messages: ['fix(auth): validate JWT signature expiration', 'revert: rollback token cache bypass'],
      },
      coverage: gNode?.coverage ?? 0.2,
      coverage_estimated: gNode?.coverage_estimated ?? true,
      is_crown_jewel: gNode?.is_crown_jewel ?? false,
      status: gNode?.status || 'normal',
      risk: gNode?.risk || 0,
      cached_summary: {
        summary: [
          `${gNode?.label || nodeId} handles core ${gNode?.kind || 'module'} logic and exposes ${(gNode?.exports || []).slice(0, 3).join(', ') || 'key entrypoints'}.`,
          `Historical git log shows a ${gNode?.defect_score || 0}/10 defect gravity score with recent hotfix activity.`,
          `Current test coverage is ${gNode?.coverage !== null && gNode?.coverage !== undefined ? Math.round(gNode.coverage * 100) + '%' : 'N/A'} (${gNode?.coverage_estimated ? 'estimated' : 'measured'}).`,
        ],
        purpose: `Primary ${gNode?.kind || 'module'} component at ${gNode?.path || nodeId}.`,
        risks: [
          gNode?.is_crown_jewel
            ? 'Crown Jewel component: downstream failures directly impact checkout or authentication.'
            : 'Changes propagate to upstream callers along reverse dependency edges.',
        ],
        exports: gNode?.exports || [],
      },
    };

    set({ nodeDetail: fallbackDetail });
    if (useMockMode || gNode?.kind === 'infra') return;

    try {
      const resp = await fetch(`/api/node/${encodeURIComponent(projectId)}/${encodeURIComponent(nodeId)}`);
      if (resp.ok) {
        const data: NodeDetailResponse = await resp.json();
        set({ nodeDetail: data });
        if (!data.cached_summary) {
          get().summarizeSelectedNode(nodeId);
        }
      }
    } catch {
      // Keep fallback detail
    }
  },

  selectEdge: (edgeId) => {
    set({ selectedEdgeId: edgeId, selectedNodeId: edgeId ? null : get().selectedNodeId });
  },

  updateNodePosition: (nodeId, pos) => {
    set((state) => ({
      graph: {
        ...state.graph,
        nodes: state.graph.nodes.map((n) => (n.id === nodeId ? { ...n, pos } : n)),
      },
    }));
  },

  summarizeSelectedNode: async (targetNodeId?: string) => {
    const nid = targetNodeId || get().selectedNodeId;
    if (!nid) return;
    const { projectId, nodeDetail } = get();
    set({ isSummarizing: true });
    try {
      const resp = await fetch(
        `/api/node/${encodeURIComponent(projectId)}/${encodeURIComponent(nid)}/summarize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: nodeDetail?.code,
            path: nodeDetail?.path || nid,
            deps: nodeDetail?.dependencies || [],
            lang: nodeDetail?.lang || 'py',
          }),
        }
      );
      if (resp.ok) {
        const summaryData: NodeSummaryData = await resp.json();
        set((state) => ({
          isSummarizing: false,
          nodeDetail: state.nodeDetail
            ? { ...state.nodeDetail, cached_summary: summaryData }
            : state.nodeDetail,
        }));
      } else {
        set({ isSummarizing: false });
      }
    } catch {
      set({ isSummarizing: false });
    }
  },

  chatWithFileNode: async (nodeId, prompt, code, history = []) => {
    const { projectId, nodeDetail } = get();
    const effectiveCode = code !== undefined ? code : nodeDetail?.code;
    try {
      const resp = await fetch(
        `/api/node/${encodeURIComponent(projectId)}/${encodeURIComponent(nodeId)}/chat`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            pid: projectId,
            nid: nodeId,
            prompt,
            code: effectiveCode,
            history,
          }),
        }
      );
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e: any) {
      console.warn('File chat failed:', e);
    }
    return {
      reply: `Analysis for ${nodeId} (${effectiveCode ? effectiveCode.split('\\n').length : 0} lines):\n\n${prompt} completed.`,
      suggested_code: null,
    };
  },

  saveNodeCode: async (nodeId, newCode) => {
    const { projectId, useMockMode, graph } = get();
    if (useMockMode) {
      const nextGraph = structuredClone(graph);
      const target = nextGraph.nodes.find((n) => n.id === nodeId);
      if (target) {
        target.churn = { added: target.churn.added + 18, deleted: target.churn.deleted + 4 };
        target.status = 'changed';
        target.risk = Math.min(100, target.risk + 15);
      }
      set((state) => ({
        graph: nextGraph,
        nodeDetail: state.nodeDetail ? { ...state.nodeDetail, code: newCode } : null,
        risk: {
          ...state.risk,
          score: Math.min(100, state.risk.score + 12),
          verdict: 'HOLD',
        },
      }));
      get().startShockwave(1);
      return;
    }

    try {
      const resp = await fetch(
        `/api/node/${encodeURIComponent(projectId)}/${encodeURIComponent(nodeId)}/code`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: newCode }),
        }
      );
      if (resp.ok) {
        const data = await resp.json();
        set((state) => ({
          graph: data.graph || state.graph,
          risk: data.risk || state.risk,
          diff: data.diff || state.diff,
          nodeDetail: state.nodeDetail ? { ...state.nodeDetail, code: newCode } : null,
        }));
        get().startShockwave(1);
      }
    } catch (err: any) {
      set({ errorBanner: `Failed to save code: ${err?.message || 'error'}` });
    }
  },

  toggleCrownJewel: async (nodeId) => {
    const { projectId, useMockMode, graph } = get();
    if (useMockMode) {
      const nextGraph = structuredClone(graph);
      const node = nextGraph.nodes.find((n) => n.id === nodeId);
      if (node) node.is_crown_jewel = !node.is_crown_jewel;
      set({ graph: nextGraph });
      return;
    }
    try {
      const resp = await fetch(
        `/api/node/${encodeURIComponent(projectId)}/${encodeURIComponent(nodeId)}/crown-jewel`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) }
      );
      if (resp.ok) {
        const data = await resp.json();
        set((state) => ({
          graph: data.graph || state.graph,
          risk: data.risk || state.risk,
          nodeDetail:
            state.nodeDetail && state.nodeDetail.id === nodeId
              ? { ...state.nodeDetail, is_crown_jewel: data.node.is_crown_jewel }
              : state.nodeDetail,
        }));
      }
    } catch {
      // ignore
    }
  },

  createSandboxNode: async (name, code, lang, isCrown) => {
    const { projectId, useMockMode, graph } = get();
    if (useMockMode) {
      const newId = name.endsWith('.py') || name.endsWith('.ts') ? name : `app/${name}.py`;
      const newNode: CNode = {
        id: newId,
        label: newId.split('/').pop() || newId,
        path: newId,
        kind: 'sandbox',
        lang: (lang as NodeLang) || 'py',
        loc: code.split('\n').length,
        churn: { added: code.split('\n').length, deleted: 0 },
        defect_score: 0,
        coverage: 0.5,
        coverage_estimated: true,
        is_crown_jewel: isCrown,
        status: 'changed',
        risk: 18,
        exports: ['rate_limit_middleware', 'check_quota'],
        pos: { x: 460, y: 200 },
      };
      set({
        graph: { ...graph, nodes: [...graph.nodes, newNode] },
        selectedNodeId: newId,
        isSandboxNodeModalOpen: false,
      });
      return;
    }

    try {
      const resp = await fetch('/api/sandbox/node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          name,
          code,
          lang: (lang as NodeLang) || 'py',
          kind: 'sandbox',
          is_crown_jewel: isCrown,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({
          graph: data.graph || get().graph,
          risk: data.risk || get().risk,
          selectedNodeId: data.node?.id || get().selectedNodeId,
          isSandboxNodeModalOpen: false,
        });
        if (data.node?.id) {
          await get().selectNode(data.node.id);
        }
      }
    } catch (err: any) {
      set({ errorBanner: `Failed to create sandbox node: ${err?.message}` });
    }
  },

  aiGenerateNode: async (prompt, lang = 'py') => {
    const { projectId } = get();
    try {
      const resp = await fetch('/api/sandbox/ai-generate-node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, prompt, lang }),
      });
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e) {
      console.warn('AI generate node failed:', e);
    }
    const cleanName = prompt.toLowerCase().includes('rate') ? 'app/rate_limiter.py' : 'app/custom_module.py';
    return {
      name: cleanName,
      code: `# Generated for: ${prompt}\n\ndef process_task(req):\n    \"\"\"Autogenerated by Local LLM.\"\"\"\n    return {"status": "ok", "task": "${prompt.slice(0, 30)}"}\n`,
      lang: (lang as 'py' | 'ts' | 'js') || 'py',
      is_crown_jewel: prompt.toLowerCase().includes('auth') || prompt.toLowerCase().includes('security'),
      suggested_inputs: ['app/auth.py'],
      suggested_outputs: ['app/redis_cache.py'],
      explanation: 'Generated task node using client offline fallback (server endpoint offline).',
    };
  },

  previewBatchWire: async (params) => {
    const { projectId, useMockMode } = get();
    set({ isBatchWiring: true });

    if (useMockMode) {
      const previewId = `batch_mock_${Date.now()}`;
      const connected_changes: NodeChangeProposal[] = [
        ...params.input_node_ids.map((nid) => ({
          node_id: nid,
          direction: 'input' as const,
          original_code: '# Existing caller code',
          modified_code: `# Existing caller code\nimport ${params.new_node_name.replace(/[^a-zA-Z0-9_]/g, '_')}\n`,
          patch: `--- a/${nid}\n+++ b/${nid}\n@@ -1,1 +1,3 @@\n+import ${params.new_node_name.replace(/[^a-zA-Z0-9_]/g, '_')}\n+# Call endpoint hook\n`,
          endpoint: `import ${params.new_node_name} -> hook()`,
          rationale: `Wires ${nid} to invoke ${params.new_node_name} as an input guard.`,
        })),
        ...params.output_node_ids.map((nid) => ({
          node_id: nid,
          direction: 'output' as const,
          original_code: '# Dependency code',
          modified_code: '# Dependency code',
          patch: `--- a/${params.new_node_name}\n+++ b/${params.new_node_name}\n@@ -1,1 +1,3 @@\n+import ${nid.replace(/[^a-zA-Z0-9_]/g, '_')}\n`,
          endpoint: `call -> ${nid}`,
          rationale: `Wires ${params.new_node_name} to invoke ${nid} as an external dependency.`,
        })),
      ];
      const previewData: BatchWirePreviewResult = {
        preview_id: previewId,
        new_node: {
          name: params.new_node_name,
          code: params.new_node_code,
          lang: params.new_node_lang,
          is_crown_jewel: params.is_crown_jewel,
        },
        connected_changes,
      };
      set({ isBatchWiring: false, batchWirePreview: previewData });
      return previewData;
    }

    try {
      const resp = await fetch('/api/sandbox/batch-wire-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, ...params }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ isBatchWiring: false, batchWirePreview: data });
        return data;
      } else {
        const errJson = await resp.json().catch(() => null);
        const errMsg = errJson?.detail?.error?.message || errJson?.detail || `HTTP ${resp.status}`;
        set({ errorBanner: `Failed to preview wiring: ${errMsg}` });
      }
    } catch (err: any) {
      set({ errorBanner: `Failed to preview wiring: ${err?.message || err}` });
    }
    set({ isBatchWiring: false });
    return null;
  },

  finalizeBatchWire: async (previewId, apply, payload) => {
    const { projectId, useMockMode, graph } = get();
    set({ isBatchWiring: true });

    if (useMockMode) {
      set({ isBatchWiring: false, batchWirePreview: null });
      if (apply && payload?.new_node) {
        const cleanName = payload.new_node.name || 'app/custom_node.py';
        const newNode: CNode = {
          id: cleanName,
          label: cleanName.split('/').pop() || cleanName,
          path: cleanName,
          kind: 'sandbox',
          lang: payload.new_node.lang || 'py',
          loc: (payload.new_node.code || '').split('\n').length || 10,
          churn: { added: 12, deleted: 0 },
          defect_score: 0,
          coverage: 0.8,
          coverage_estimated: true,
          is_crown_jewel: !!payload.new_node.is_crown_jewel,
          status: 'changed',
          risk: 20,
          exports: ['handler'],
          pos: { x: 450, y: 220 },
        };
        const nextNodes = [...graph.nodes, newNode];
        const nextEdges = [...graph.edges];
        (payload.connected_changes || []).forEach((c: any) => {
          if (c.direction === 'input') {
            nextEdges.push({ id: `e-${c.node_id}-${cleanName}`, source: c.node_id, target: cleanName, type: 'call', weight: 0.9 });
          } else {
            nextEdges.push({ id: `e-${cleanName}-${c.node_id}`, source: cleanName, target: c.node_id, type: 'call', weight: 0.9 });
          }
        });
        set({ graph: { ...graph, nodes: nextNodes, edges: nextEdges }, isSandboxNodeModalOpen: false, selectedNodeId: cleanName });
        get().startShockwave(1);
      } else {
        set({ isSandboxNodeModalOpen: false });
      }
      return true;
    }

    try {
      const resp = await fetch('/api/sandbox/batch-wire-finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, preview_id: previewId, apply, payload }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ isBatchWiring: false, batchWirePreview: null });
        if (apply) {
          await get().fetchInitialWorkspace(projectId);
          if (data.new_node_id) {
            await get().selectNode(data.new_node_id);
          }
          get().startShockwave(1);
          set({ isSandboxNodeModalOpen: false });
        }
        return true;
      }
    } catch (err: any) {
      set({ errorBanner: `Failed to finalize batch wire: ${err?.message || err}` });
    }
    set({ isBatchWiring: false });
    return false;
  },

  proposeEdgeConnection: async (sourceId, targetId) => {
    if (!sourceId || !targetId || sourceId === targetId) return;
    const { projectId, useMockMode } = get();
    set({ isConnectingNodes: true });

    if (useMockMode) {
      set({
        isConnectingNodes: false,
        pendingConnectProposal: {
          proposal_id: `prop_mock_${Date.now()}`,
          source_node_id: sourceId,
          target_node_id: targetId,
          endpoint: `import ${targetId.split('/').pop()?.replace('.py', '')} -> enforce_rate_limit()`,
          rationale: `Wires ${sourceId} to invoke ${targetId} before processing unauthenticated requests, reducing blast radius exposure on Crown Jewel components.`,
          patch: `--- a/${sourceId}\n+++ b/${sourceId}\n@@ -1,4 +1,6 @@\n+from ${targetId.replace('.py', '').replace('/', '.')} import check_rate_limit\n \n def handle_request(req):\n+    check_rate_limit(req.client_ip)\n     return process(req)\n`,
        },
      });
      return;
    }

    try {
      const resp = await fetch('/api/sandbox/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          source_node_id: sourceId,
          target_node_id: targetId,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({
          isConnectingNodes: false,
          pendingConnectProposal: {
            ...data,
            source_node_id: sourceId,
            target_node_id: targetId,
          },
        });
      } else {
        await fetch('/api/sandbox/edge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pid: projectId, source: sourceId, target: targetId, type: 'call', action: 'add' }),
        });
        await get().fetchInitialWorkspace(projectId);
        set({ isConnectingNodes: false });
      }
    } catch {
      set({ isConnectingNodes: false });
    }
  },

  applyEdgeConnection: async (proposalId) => {
    const { projectId, pendingConnectProposal, useMockMode, graph, risk } = get();
    if (!pendingConnectProposal) return;

    const src = pendingConnectProposal.source_node_id || '';
    const dst = pendingConnectProposal.target_node_id || '';

    if (useMockMode) {
      const newEdge: CEdge = {
        id: `e-${src}-${dst}`,
        source: src,
        target: dst,
        type: 'call',
        weight: 0.9,
      };
      const newScore = Math.max(24, risk.score - 22);
      set({
        graph: { ...graph, edges: [...graph.edges, newEdge] },
        risk: {
          ...risk,
          score: newScore,
          verdict: newScore < 35 ? 'GO' : newScore <= 65 ? 'CAUTION' : 'HOLD',
        },
        pendingConnectProposal: null,
      });
      return;
    }

    try {
      await fetch('/api/sandbox/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, proposal_id: proposalId }),
      });
      set({ pendingConnectProposal: null });
      await get().fetchInitialWorkspace(projectId);
      get().startShockwave(1);
    } catch {
      set({ pendingConnectProposal: null });
    }
  },

  severEdge: async (edgeId) => {
    const { projectId, graph, useMockMode } = get();
    const edge = graph.edges.find((e) => e.id === edgeId);
    if (!edge) return;

    if (useMockMode) {
      set({
        graph: { ...graph, edges: graph.edges.filter((e) => e.id !== edgeId) },
        selectedEdgeId: null,
      });
      return;
    }

    await fetch('/api/sandbox/edge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pid: projectId,
        source: edge.source,
        target: edge.target,
        action: 'remove',
      }),
    });
    set({ selectedEdgeId: null });
    await get().fetchInitialWorkspace(projectId);
  },

  triggerDockerRunWithShockwave: () => {
    get().startShockwave(1);
    set((state) => ({
      isTerminalOpen: true,
      dockerAutoRunCounter: state.dockerAutoRunCounter + 1,
    }));
  },

  runTests: async (onlyImpacted = false, customTestCode?: string) => {
    const { projectId, risk, selectedNodeId } = get();
    set({ isRunningTests: true });
    // Automatically animate the shockwave as tests run in Docker!
    get().startShockwave(1);
    try {
      const targetNodes = onlyImpacted
        ? risk.impacted.map((i) => i.id)
        : selectedNodeId
        ? [selectedNodeId]
        : undefined;
      const resp = await fetch('/api/tests/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          node_ids: targetNodes,
          test_code: customTestCode || undefined,
          wait: true,
        }),
      });
      if (resp.ok) {
        const resData = await resp.json();
        set({ lastTestRun: resData, isRunningTests: false });
        await get().fetchInitialWorkspace(projectId);
        get().startShockwave(1);
      } else {
        set({ isRunningTests: false });
      }
    } catch {
      set({ isRunningTests: false });
    }
  },

  generateTestsForNode: async (nodeId) => {
    const { projectId, nodeDetail } = get();
    set({ isGeneratingTests: true });
    try {
      const resp = await fetch('/api/tests/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          nid: nodeId,
          code: nodeDetail?.code,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({
          generatedTestCode: data.test_code || '',
          isGeneratingTests: false,
          activeInspectorTab: 'risk',
        });
      } else {
        set({ isGeneratingTests: false });
      }
    } catch {
      set({ isGeneratingTests: false });
    }
  },

  runAgentLoop: async (promptText) => {
    const { projectId, agentPrompt } = get();
    const prompt = promptText || agentPrompt;
    if (!prompt.trim()) return;
    set({ isRunningAgent: true, agentResult: null });
    try {
      const resp = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, prompt }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ agentResult: data, isRunningAgent: false });
      } else {
        set({ isRunningAgent: false });
      }
    } catch {
      set({ isRunningAgent: false });
    }
  },

  runAntiPatternScan: async (nodeId) => {
    const { projectId, nodeDetail } = get();
    try {
      const resp = await fetch('/api/stretch/antipatterns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          nid: nodeId,
          path: nodeDetail?.path || nodeId,
          code: nodeDetail?.code,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ antiPatternResult: data });
      }
    } catch {
      // ignore
    }
  },

  runConflictResolver: async (filePath) => {
    const { projectId, merge } = get();
    const targetPath = filePath || merge.conflicts[0]?.path || 'app/auth.py';
    try {
      const resp = await fetch('/api/stretch/resolve-conflict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: projectId, path: targetPath }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ conflictResolutionResult: data });
      }
    } catch {
      // ignore
    }
  },

  runAutoHeal: async () => {
    const { projectId, selectedNodeId, lastTestRun, generatedTestCode } = get();
    const trace =
      lastTestRun?.failures?.[0]?.message ||
      lastTestRun?.output ||
      'AssertionError: expected status 200 but got 401 in test_auth_token';
    try {
      const resp = await fetch('/api/stretch/auto-heal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pid: projectId,
          nid: selectedNodeId || 'app/auth.py',
          stack_trace: trace,
          test_code: generatedTestCode,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        set({ autoHealResult: data });
        if (data.healed_test_code) {
          set({ generatedTestCode: data.healed_test_code });
        }
      }
    } catch {
      // ignore
    }
  },

  fetchComparison: async (base = 'origin/main', head = 'HEAD') => {
    const { projectId } = get();
    try {
      const resp = await fetch(
        `/api/compare/${encodeURIComponent(projectId)}?base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`
      );
      if (resp.ok) {
        const data: ReleaseComparisonResult = await resp.json();
        set({ comparison: data });
      }
    } catch {
      // ignore
    }
  },

  testLlmConnection: async () => {
    try {
      const resp = await fetch('/api/llm/test', { method: 'POST' });
      if (resp.ok) {
        return await resp.json();
      }
      return { status: 'error', error: `Server returned HTTP ${resp.status}` };
    } catch (err: any) {
      return { status: 'error', error: err?.message || 'Connection test failed' };
    }
  },

  updateLlmConfig: async (apiKey: string, model?: string) => {
    try {
      const resp = await fetch('/api/llm/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, model }),
      });
      if (resp.ok) {
        const nextStatus = await resp.json();
        set({ llmStatus: nextStatus });
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  startShockwave: (speed = 1) => {
    if (shockwaveTimer) {
      clearInterval(shockwaveTimer);
      shockwaveTimer = null;
    }
    const impacted = get().risk.impacted || [];
    const maxDepth = impacted.reduce((acc, item) => Math.max(acc, item.depth), 2);
    set({ shockwaveStep: 0, isShockwavePlaying: true, shockwaveSpeed: speed });

    const intervalMs = Math.max(180, Math.round(320 / speed));
    shockwaveTimer = setInterval(() => {
      const curr = get().shockwaveStep ?? 0;
      if (curr >= maxDepth) {
        if (shockwaveTimer) {
          clearInterval(shockwaveTimer);
          shockwaveTimer = null;
        }
        set({ isShockwavePlaying: false, shockwaveStep: null });
      } else {
        set({ shockwaveStep: curr + 1 });
      }
    }, intervalMs);
  },

  pauseShockwave: () => {
    if (shockwaveTimer) {
      clearInterval(shockwaveTimer);
      shockwaveTimer = null;
    }
    set({ isShockwavePlaying: false });
  },

  resetShockwave: () => {
    if (shockwaveTimer) {
      clearInterval(shockwaveTimer);
      shockwaveTimer = null;
    }
    set({ isShockwavePlaying: false, shockwaveStep: null });
  },

  setShockwaveStep: (step) => {
    if (shockwaveTimer) {
      clearInterval(shockwaveTimer);
      shockwaveTimer = null;
    }
    set({ isShockwavePlaying: false, shockwaveStep: step });
  },

  startExecutionTrace: (initialNodeId?: string) => {
    const state = get();
    let targetId = initialNodeId;
    if (!targetId) {
      const entry =
        state.graph.nodes.find(
          (n) =>
            n.kind === 'service' ||
            n.kind === 'route' ||
            n.status === 'changed' ||
            n.is_crown_jewel ||
            n.id.includes('main') ||
            n.id.includes('server') ||
            n.id.includes('app')
        ) || state.graph.nodes[0];
      if (entry) targetId = entry.id;
    }
    const executing = targetId ? [targetId] : [];
    const flowEdges = targetId
      ? state.graph.edges
          .filter((e) => e.source === targetId || e.target === targetId)
          .map((e) => e.id)
      : [];
    set({
      isProgramRunning: true,
      executingNodeIds: executing,
      activeFlowEdgeIds: flowEdges,
    });
  },

  setExecutingNode: (nodeIdOrPath: string) => {
    const state = get();
    const clean = nodeIdOrPath.replace(/\\/g, '/').replace(/^\.\//, '').trim();
    const base = clean.split('/').pop() || clean;

    const matched = state.graph.nodes.find((n) => {
      const nId = n.id.replace(/\\/g, '/');
      const nPath = (n.path || '').replace(/\\/g, '/');
      const nLabel = n.label || '';
      return (
        nId === clean ||
        nPath === clean ||
        nLabel === clean ||
        nId.endsWith(clean) ||
        clean.endsWith(nId) ||
        nId.endsWith('/' + base) ||
        nLabel === base ||
        nPath.endsWith('/' + base)
      );
    });

    const activeId = matched ? matched.id : clean;
    const currentExec = new Set(state.executingNodeIds || []);
    currentExec.add(activeId);

    const newFlowEdges = state.graph.edges
      .filter((e) => e.source === activeId || e.target === activeId)
      .map((e) => e.id);

    const mergedEdges = Array.from(new Set([...(state.activeFlowEdgeIds || []), ...newFlowEdges]));

    set({
      isProgramRunning: true,
      executingNodeIds: Array.from(currentExec),
      activeFlowEdgeIds: mergedEdges,
    });

    setTimeout(() => {
      const s = get();
      if (!s.isProgramRunning) return;
      if (s.executingNodeIds.length > 1) {
        set({
          executingNodeIds: s.executingNodeIds.filter((id) => id !== activeId),
        });
      }
    }, 2800);
  },

  stopExecutionTrace: () => {
    set({
      isProgramRunning: false,
      executingNodeIds: [],
      activeFlowEdgeIds: [],
    });
  },

  applyWsEvent: (envelope) => {
    if (envelope.project_id && envelope.project_id !== get().projectId) {
      return;
    }
    const { type, payload } = envelope;
    switch (type) {
      case 'node_pulse':
        if (payload && ((payload as any).node_id || (payload as any).path)) {
          get().setExecutingNode((payload as any).node_id || (payload as any).path);
        }
        break;
      case 'active_nodes':
        if (payload && Array.isArray((payload as any).node_ids)) {
          for (const nid of (payload as any).node_ids) {
            get().setExecutingNode(nid);
          }
        }
        break;
      case 'graph_loaded':
        if (payload && (payload as Graph).nodes) {
          set({ graph: payload as Graph });
        }
        break;
      case 'risk_updated':
        if (payload && typeof (payload as RiskResult).score === 'number') {
          set({ risk: payload as RiskResult });
        }
        break;
      case 'diff_updated':
        if (payload && Array.isArray((payload as DiffResult).files)) {
          set({ diff: payload as DiffResult });
        }
        break;
      case 'merge_checked':
        if (payload && typeof (payload as MergeResult).clean === 'boolean') {
          set({ merge: payload as MergeResult });
        }
        break;
      case 'test_run_finished':
        if (payload) {
          const tr = payload as TestRunResult;
          set({ lastTestRun: tr, isRunningTests: false });
          const failedNodeIds = new Set(
            (tr.failures || []).map((f) => f.node_id).filter(Boolean) as string[]
          );
          if (failedNodeIds.size > 0) {
            set((state) => ({
              graph: {
                ...state.graph,
                nodes: state.graph.nodes.map((n) =>
                  failedNodeIds.has(n.id) || failedNodeIds.has(n.label)
                    ? { ...n, status: 'failing' }
                    : n
                ),
              },
            }));
          }
          get().startShockwave(1);
        }
        break;
      case 'coverage_updated':
        if (payload && (payload as any).coverage) {
          const covMap = (payload as any).coverage as Record<string, number>;
          set((state) => ({
            graph: {
              ...state.graph,
              nodes: state.graph.nodes.map((n) => {
                const measured = covMap[n.id] ?? covMap[n.label];
                return measured !== undefined
                  ? { ...n, coverage: measured, coverage_estimated: false }
                  : n;
              }),
            },
          }));
        }
        break;
      case 'impact_computed':
        get().startShockwave(1);
        break;
      default:
        break;
    }
  },
}));
