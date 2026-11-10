import { create } from 'zustand';
import {
  Graph,
  GraphEvent,
  SimResult,
  ScorecardComparison,
  GNode,
  GEdge,
} from '../../../shared/types';
import { simulate } from '../engine/simulate';
import sampleTopology from '../../../shared/topology.sample.json';

export type ActiveTool = 'select' | 'scissors' | 'patch';

export type SimPlaybackStatus = 'idle' | 'running' | 'paused' | 'completed' | 'trapped' | 'blocked';

export interface SimPlaybackState {
  status: SimPlaybackStatus;
  currentHop: number; // -1 when idle
  speed: number;      // 1, 2, 4
  revealedNodes: string[]; // Node IDs that have been compromised during this run
  revealedEdges: string[]; // Edge IDs that have been traversed during this run
  activeEdgeId: string | null; // Edge currently having active photon traversal
  targetNodeId: string | null; // Node currently under assault
  progressPercent: number;     // 0 to 100%
  statusMessage: string;       // Human-readable status string
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'info' | 'danger';
  title: string;
  message: string;
  timestamp: number;
}

interface GraphStoreState {
  liveGraph: Graph;
  whatIfGraph: Graph;
  mode: 'live' | 'whatif';
  activeTool: ActiveTool;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  sim: SimResult;
  baselineSim: SimResult | null;
  connected: boolean;
  eventsLog: GraphEvent[];
  playbackStep: number | null;
  activeToast: ToastMessage | null;
  simPlayback: SimPlaybackState;

  // Actions
  setConnected: (status: boolean) => void;
  applySnapshot: (graph: Graph) => void;
  applyEvent: (event: GraphEvent) => void;
  setMode: (mode: 'live' | 'whatif') => void;
  fork: () => void;
  setActiveTool: (tool: ActiveTool) => void;
  selectNode: (id: string | null) => void;
  selectEdge: (id: string | null) => void;
  setPlaybackStep: (step: number | null) => void;
  showToast: (toast: Omit<ToastMessage, 'id' | 'timestamp'>) => void;
  clearToast: () => void;

  // Live Attack Simulation Playback Controls
  startSimulation: () => void;
  pauseSimulation: () => void;
  resumeSimulation: () => void;
  resetSimulation: () => void;
  replaySimulation: () => void;
  setSimSpeed: (speed: number) => void;
  advanceSimulationStep: () => void;

  // Defense Actions (Works in What-if mode, auto-forks if in live mode)
  firewallEdge: (edgeId: string) => void;
  patchNode: (nodeId: string) => void;
  deployDecoy: () => void;
  resetWhatIf: () => void;

  // Helpers
  getActiveGraph: () => Graph;
  getScorecard: () => ScorecardComparison;
}

const cloneGraph = (g: Graph): Graph => JSON.parse(JSON.stringify(g));

function computeRiskScore(sim: SimResult): number {
  const ratio = sim.blastRadius.total > 0 ? sim.blastRadius.compromised / sim.blastRadius.total : 0;
  let score = Math.round(ratio * 60);
  if (sim.reachedCrownJewel) {
    const speedFactor = sim.timeToCrownSec ? Math.max(0, 40 - Math.min(35, Math.floor(sim.timeToCrownSec / 2))) : 40;
    score += speedFactor;
  }
  return Math.min(100, Math.max(5, score));
}

let recomputeTimer: ReturnType<typeof setTimeout> | null = null;
let simInterval: ReturnType<typeof setInterval> | null = null;

const stopSimTimer = () => {
  if (simInterval) {
    clearInterval(simInterval);
    simInterval = null;
  }
};

const initialGraph = cloneGraph(sampleTopology as unknown as Graph);
const initialSim = simulate(initialGraph);

const initialPlaybackState: SimPlaybackState = {
  status: 'idle',
  currentHop: -1,
  speed: 1,
  revealedNodes: [],
  revealedEdges: [],
  activeEdgeId: null,
  targetNodeId: null,
  progressPercent: 0,
  statusMessage: 'Standby • Ready for simulation run',
};

export const useGraphStore = create<GraphStoreState>((set, get) => {
  const triggerDebouncedSim = () => {
    if (recomputeTimer) clearTimeout(recomputeTimer);
    recomputeTimer = setTimeout(() => {
      const activeGraph = get().mode === 'live' ? get().liveGraph : get().whatIfGraph;
      set({ sim: simulate(activeGraph) });
    }, 200);
  };

  return {
    liveGraph: initialGraph,
    whatIfGraph: cloneGraph(initialGraph),
    mode: 'live',
    activeTool: 'select',
    selectedNodeId: null,
    selectedEdgeId: null,
    sim: initialSim,
    baselineSim: initialSim,
    connected: false,
    eventsLog: [],
    playbackStep: null,
    activeToast: null,
    simPlayback: initialPlaybackState,

    setConnected: (connected) => set({ connected }),

    showToast: (toast) => {
      const id = 'toast-' + Date.now();
      set({
        activeToast: {
          ...toast,
          id,
          timestamp: Date.now(),
        },
      });
      setTimeout(() => {
        if (get().activeToast?.id === id) {
          set({ activeToast: null });
        }
      }, 4500);
    },

    clearToast: () => set({ activeToast: null }),

    applySnapshot: (graph) => {
      stopSimTimer();
      const copy = cloneGraph(graph);
      const newSim = simulate(copy);
      set((state) => ({
        liveGraph: copy,
        whatIfGraph: state.mode === 'live' ? cloneGraph(copy) : state.whatIfGraph,
        sim: state.mode === 'live' ? newSim : state.sim,
        baselineSim: state.mode === 'live' ? newSim : state.baselineSim,
        simPlayback: initialPlaybackState,
        playbackStep: null,
      }));
    },

    applyEvent: (ev) => {
      set((state) => {
        const g = cloneGraph(state.liveGraph);
        const payload = (ev.payload || {}) as Record<string, any>;

        switch (ev.type) {
          case 'node_added':
            g.nodes.push({ id: ev.id, ...(payload as Partial<GNode>), lastSource: ev.source } as GNode);
            break;
          case 'node_removed':
            g.nodes = g.nodes.filter((n) => n.id !== ev.id);
            break;
          case 'node_updated':
            g.nodes = g.nodes.map((n) =>
              n.id === ev.id ? { ...n, ...payload, lastSource: ev.source } : n
            );
            break;
          case 'node_compromised':
            g.nodes = g.nodes.map((n) =>
              n.id === ev.id
                ? { ...n, ...payload, status: 'compromised', lastSource: ev.source }
                : n
            );
            break;
          case 'cve_found':
            g.nodes = g.nodes.map((n) => {
              if (n.id !== ev.id) return n;
              const merged = Array.from(
                new Set([...(n.vulnerabilities || []), ...(payload.vulnerabilities || [])])
              );
              return {
                ...n,
                vulnerabilities: merged,
                cvss_score: payload.cvss_score ?? n.cvss_score,
                lastSource: ev.source,
              };
            });
            break;
          case 'edge_added':
            g.edges.push({ id: ev.id, ...(payload as Partial<GEdge>) } as GEdge);
            break;
          case 'edge_removed':
            g.edges = g.edges.filter((e) => e.id !== ev.id);
            break;
          case 'edge_updated':
            g.edges = g.edges.map((e) => (e.id === ev.id ? { ...e, ...payload } : e));
            break;
          case 'edge_active_attack':
            g.edges = g.edges.map((e) =>
              e.id === ev.id ? { ...e, ...payload, status: 'active_attack' } : e
            );
            break;
        }

        return {
          liveGraph: g,
          eventsLog: [ev, ...state.eventsLog].slice(0, 100),
        };
      });
      if (get().mode === 'live') {
        triggerDebouncedSim();
      }
    },

    fork: () => {
      stopSimTimer();
      const liveCopy = cloneGraph(get().liveGraph);
      const baseSim = simulate(liveCopy);
      set({
        whatIfGraph: liveCopy,
        baselineSim: baseSim,
        sim: baseSim,
        playbackStep: null,
        simPlayback: initialPlaybackState,
      });
    },

    setMode: (mode) => {
      stopSimTimer();
      if (mode === 'whatif') {
        get().fork();
        set({ mode: 'whatif', simPlayback: initialPlaybackState });
        get().showToast({
          type: 'info',
          title: 'WHAT-IF LAB ACTIVATED',
          message: 'Changes are safely isolated from live production telemetry.',
        });
      } else {
        const liveSim = simulate(get().liveGraph);
        set({
          mode: 'live',
          activeTool: 'select',
          selectedEdgeId: null,
          sim: liveSim,
          playbackStep: null,
          simPlayback: initialPlaybackState,
        });
        get().showToast({
          type: 'info',
          title: 'LIVE TELEMETRY MODE',
          message: 'Viewing real-time production infrastructure.',
        });
      }
    },

    setActiveTool: (activeTool) => set({ activeTool }),
    selectNode: (selectedNodeId) => set({ selectedNodeId, selectedEdgeId: null }),
    selectEdge: (selectedEdgeId) => set({ selectedEdgeId, selectedNodeId: null }),
    setPlaybackStep: (playbackStep) => set({ playbackStep }),

    /* ---------------------------------------------------------------------- */
    /*              STEP-BY-STEP LIVE ATTACK SIMULATION ENGINE               */
    /* ---------------------------------------------------------------------- */
    startSimulation: () => {
      stopSimTimer();

      const activeGraph = get().getActiveGraph();
      const sim = simulate(activeGraph);
      set({ sim });

      if (sim.path.length <= 1) {
        set({
          simPlayback: {
            status: sim.reachedCrownJewel ? 'completed' : 'blocked',
            currentHop: 0,
            speed: get().simPlayback.speed,
            revealedNodes: sim.path,
            revealedEdges: [],
            activeEdgeId: null,
            targetNodeId: null,
            progressPercent: 100,
            statusMessage: sim.path.length === 0
              ? 'All ingress and lateral attack paths blocked by defenses.'
              : 'Initial asset compromised, but lateral movement is severed.',
          },
        });
        get().showToast({
          type: 'warning',
          title: 'ATTACK BLOCKED',
          message: 'No viable lateral paths to Crown Jewel or Decoy assets.',
        });
        return;
      }

      // Step 0: Initial entry node compromised
      const initialNode = sim.path[0];
      const nextNode = sim.path[1];
      const initialEdge = sim.edgesUsed[0] || null;

      set({
        playbackStep: 0,
        simPlayback: {
          status: 'running',
          currentHop: 0,
          speed: get().simPlayback.speed,
          revealedNodes: [initialNode],
          revealedEdges: [],
          activeEdgeId: initialEdge,
          targetNodeId: nextNode,
          progressPercent: Math.round((1 / sim.path.length) * 100),
          statusMessage: "Initial breach on " + (activeGraph.nodes.find((n) => n.id === initialNode)?.label || initialNode) + ". Infiltrating lateral conduit...",
        },
      });

      get().showToast({
        type: 'info',
        title: 'LIVE ATTACK PROPAGATION STARTED',
        message: "Tracing dynamic adversary lateral movement across " + sim.path.length + " assets.",
      });

      const intervalMs = Math.max(500, 1600 / get().simPlayback.speed);
      simInterval = setInterval(() => {
        get().advanceSimulationStep();
      }, intervalMs);
    },

    advanceSimulationStep: () => {
      const { simPlayback, sim } = get();
      if (simPlayback.status !== 'running') return;

      const activeGraph = get().getActiveGraph();
      const nextHop = simPlayback.currentHop + 1;

      if (nextHop >= sim.path.length) {
        stopSimTimer();
        const isTrapped = sim.trappedByDecoy;
        const reachedCrown = sim.reachedCrownJewel;

        set({
          simPlayback: {
            ...simPlayback,
            status: isTrapped ? 'trapped' : reachedCrown ? 'completed' : 'blocked',
            currentHop: sim.path.length - 1,
            activeEdgeId: null,
            targetNodeId: null,
            progressPercent: 100,
            statusMessage: isTrapped
              ? (get().sim.stopReason || 'Adversary trapped! Diverted into Honeypot Decoy Vault.')
              : reachedCrown
              ? (get().sim.stopReason || 'CRITICAL ALERT: Production Crown Jewel Database reached!')
              : (get().sim.stopReason || 'Attack halted: Lateral path severed.'),
          },
        });

        get().showToast({
          type: isTrapped ? 'success' : reachedCrown ? 'danger' : 'info',
          title: isTrapped ? 'ATTACK CONTAINED' : reachedCrown ? 'CROWN JEWEL BREACHED' : 'SIMULATION ENDED',
          message: isTrapped
            ? 'Threat contained in decoy. Lateral movement to production assets diverted.'
            : reachedCrown
            ? 'Adversary reached Crown Jewel Database. Deploy firewall or patch CVEs to break chain.'
            : 'Adversary reached end of traversal without breaching Crown Jewel.',
        });
        return;
      }

      const traversedEdge = sim.edgesUsed[simPlayback.currentHop];
      const reachedNodeId = sim.path[nextHop];
      const nextEdge = sim.edgesUsed[nextHop] || null;
      const nextTarget = sim.path[nextHop + 1] || null;

      const newRevealedEdges = traversedEdge
        ? Array.from(new Set([...simPlayback.revealedEdges, traversedEdge]))
        : simPlayback.revealedEdges;

      const newRevealedNodes = Array.from(new Set([...simPlayback.revealedNodes, reachedNodeId]));
      const reachedNode = activeGraph.nodes.find((n) => n.id === reachedNodeId);

      if (reachedNode?.is_decoy) {
        stopSimTimer();
        set({
          playbackStep: nextHop,
          simPlayback: {
            status: 'trapped',
            currentHop: nextHop,
            speed: simPlayback.speed,
            revealedNodes: newRevealedNodes,
            revealedEdges: newRevealedEdges,
            activeEdgeId: null,
            targetNodeId: null,
            progressPercent: 100,
            statusMessage: "Attacker breached " + reachedNode.label + "! Honeypot trap triggered; lateral movement contained.",
          },
        });
        get().showToast({
          type: 'success',
          title: 'HONEYPOT TRAP TRIGGERED',
          message: reachedNode.label + " trapped adversary. Production assets shielded!",
        });
        return;
      }

      set({
        playbackStep: nextHop,
        simPlayback: {
          ...simPlayback,
          currentHop: nextHop,
          revealedNodes: newRevealedNodes,
          revealedEdges: newRevealedEdges,
          activeEdgeId: nextEdge,
          targetNodeId: nextTarget,
          progressPercent: Math.round(((nextHop + 1) / sim.path.length) * 100),
          statusMessage: "Compromised " + (reachedNode?.label || reachedNodeId) + ". " + (nextTarget ? "Pivoting to " + (activeGraph.nodes.find((n) => n.id === nextTarget)?.label || nextTarget) + "..." : 'Objective reached.'),
        },
      });
    },

    pauseSimulation: () => {
      stopSimTimer();
      set((s) => ({
        simPlayback: {
          ...s.simPlayback,
          status: 'paused',
          statusMessage: 'Simulation paused',
        },
      }));
    },

    resumeSimulation: () => {
      stopSimTimer();
      set((s) => ({
        simPlayback: {
          ...s.simPlayback,
          status: 'running',
          statusMessage: 'Resuming attack traversal...',
        },
      }));
      const intervalMs = Math.max(500, 1600 / get().simPlayback.speed);
      simInterval = setInterval(() => {
        get().advanceSimulationStep();
      }, intervalMs);
    },

    resetSimulation: () => {
      stopSimTimer();
      set({
        playbackStep: null,
        simPlayback: {
          ...initialPlaybackState,
          speed: get().simPlayback.speed,
        },
      });
      get().showToast({
        type: 'info',
        title: 'SIMULATION RESET',
        message: 'Attack path cleared. Normal infrastructure topology restored.',
      });
    },

    replaySimulation: () => {
      get().resetSimulation();
      get().startSimulation();
    },

    setSimSpeed: (speed) => {
      set((s) => ({
        simPlayback: { ...s.simPlayback, speed },
      }));
      if (get().simPlayback.status === 'running') {
        stopSimTimer();
        const intervalMs = Math.max(500, 1600 / speed);
        simInterval = setInterval(() => {
          get().advanceSimulationStep();
        }, intervalMs);
      }
    },

    /* ---------------------------------------------------------------------- */
    /*                         DEFENSE ACTIONS                                */
    /* ---------------------------------------------------------------------- */
    firewallEdge: (edgeId) => {
      if (get().mode !== 'whatif') {
        get().fork();
        set({ mode: 'whatif' });
      }

      stopSimTimer();
      const g = cloneGraph(get().whatIfGraph);
      let wasFirewalled = false;
      let targetEdge: GEdge | undefined;

      g.edges = g.edges.map((e) => {
        if (e.id === edgeId) {
          targetEdge = e;
          wasFirewalled = e.status === 'firewalled';
          return { ...e, status: wasFirewalled ? 'open' : 'firewalled' };
        }
        return e;
      });

      let newSim = simulate(g);
      // If the attack still reaches Crown Jewel but via a different route, mark as rerouted
      const baseEdges = get().baselineSim?.edgesUsed ?? [];
      if (newSim.routeStatus === 'optimal' && JSON.stringify(baseEdges) !== JSON.stringify(newSim.edgesUsed)) {
        newSim = { ...newSim, routeStatus: 'rerouted',
          stopReason: 'Primary route severed. Attacker rerouted via alternative path: ' + newSim.path.join(' → ') + '. Deploy additional defenses to block this route.' };
      }
      set({
        whatIfGraph: g,
        sim: newSim,
        playbackStep: null,
        simPlayback: {
          ...initialPlaybackState,
          speed: get().simPlayback.speed,
        },
      });

      if (wasFirewalled) {
        get().showToast({
          type: 'info',
          title: 'CONNECTION RESTORED',
          message: "Pathway " + edgeId + " (" + (targetEdge?.protocol || 'Network') + ") unblocked. Attack path recalculated.",
        });
      } else {
        const rs = newSim.routeStatus;
        const toastType = rs === 'blocked' || rs === 'trapped_in_decoy' || rs === 'no_entry' ? 'success' : 'warning';
        const toastTitle =
          rs === 'blocked' ? 'CROWN JEWEL ISOLATED' :
          rs === 'trapped_in_decoy' ? 'ATTACKER DIVERTED TO DECOY' :
          rs === 'no_entry' ? 'ATTACK HALTED' :
          'FIREWALL DEPLOYED — REROUTE DETECTED';
        get().showToast({
          type: toastType,
          title: toastTitle,
          message: newSim.stopReason,
        });
      }
    },

    patchNode: (nodeId) => {
      if (get().mode !== 'whatif') {
        get().fork();
        set({ mode: 'whatif' });
      }

      stopSimTimer();
      const g = cloneGraph(get().whatIfGraph);
      let patchedNodeLabel = nodeId;

      g.nodes = g.nodes.map((n) => {
        if (n.id === nodeId) {
          patchedNodeLabel = n.label;
          return {
            ...n,
            vulnerabilities: [],
            cvss_score: 0.0,
            status: 'secure',
          };
        }
        return n;
      });

      const newSim = simulate(g);
      set({
        whatIfGraph: g,
        sim: newSim,
        playbackStep: null,
        simPlayback: {
          ...initialPlaybackState,
          speed: get().simPlayback.speed,
        },
      });

      const prevented = !newSim.reachedCrownJewel;
      get().showToast({
        type: prevented ? 'success' : 'info',
        title: 'ASSET PATCHED & SHIELDED',
        message: prevented
          ? "All CVEs on " + patchedNodeLabel + " remediated! Crown jewel attack CHAIN BROKEN!"
          : "All CVEs on " + patchedNodeLabel + " remediated. Attacker recalculating route...",
      });
    },

    deployDecoy: () => {
      if (get().mode !== 'whatif') {
        get().fork();
        set({ mode: 'whatif' });
      }

      const g = cloneGraph(get().whatIfGraph);
      const existingDecoys = g.nodes.filter((n) => n.is_decoy);
      const decoyCount = existingDecoys.length;

      if (decoyCount >= 3) {
        get().showToast({
          type: 'warning',
          title: 'MAX DECOYS REACHED',
          message: 'Maximum honeypot cluster capacity (3) reached.',
        });
        return;
      }

      const decoyIndex = decoyCount + 1;
      const decoyId = "node-decoy-honeypot-" + decoyIndex;
      const decoyPositions = [
        { x: 500, y: 560 },
        { x: 740, y: 520 },
        { x: 300, y: 520 },
      ];
      const pos = decoyPositions[decoyCount] || { x: 500, y: 560 };

      const decoyNode: GNode = {
        id: decoyId,
        label: decoyCount === 0 ? 'Decoy Honeypot Vault' : "Decoy Bait Server #" + decoyIndex,
        type: 'Decoy',
        cvss_score: 10.0,
        vulnerabilities: ["CVE-2024-HONEY-" + decoyIndex],
        is_crown_jewel: false,
        is_decoy: true,
        status: 'secure',
        refs: { ip: "10.0.50." + (90 + decoyIndex), hostname: "honeypot-vault-0" + decoyIndex },
        pos,
      };

      g.nodes.push(decoyNode);

      // Connect decoy enticingly to all major lateral pivot nodes in the topology
      const attachCandidates = [
        'node-printer-01',
        'node-dev-laptop',
        'node-sre-workstation',
        'node-build-srv',
        'node-app-server',
      ];

      attachCandidates.forEach((srcId) => {
        if (g.nodes.some((n) => n.id === srcId)) {
          g.edges.push({
            id: "edge-decoy-" + decoyIndex + "-" + srcId.replace('node-', ''),
            source: srcId,
            target: decoyId,
            protocol: 'SSH',
            exploit_time_sec: 1.5,
            status: 'open',
          });
        }
      });

      const newSim = simulate(g);
      stopSimTimer();

      set({
        whatIfGraph: g,
        sim: newSim,
        playbackStep: null,
        simPlayback: {
          ...initialPlaybackState,
          speed: get().simPlayback.speed,
        },
      });

      get().showToast({
        type: 'success',
        title: decoyCount === 0 ? 'HONEYPOT VAULT DEPLOYED' : "DECOY #" + decoyIndex + " ARMED",
        message: 'Bait credentials seeded. Attacker will be diverted into containment trap.',
      });
    },

    resetWhatIf: () => {
      stopSimTimer();
      get().fork();
      get().showToast({
        type: 'info',
        title: 'WHAT-IF RESET',
        message: 'Reverted What-If sandbox to baseline production snapshot.',
      });
    },

    getActiveGraph: () => (get().mode === 'live' ? get().liveGraph : get().whatIfGraph),

    getScorecard: () => {
      const base = get().baselineSim || get().sim;
      const curr = get().sim;
      return {
        baseline: {
          blastRadius: base.blastRadius,
          timeToCrownSec: base.timeToCrownSec,
          riskScore: computeRiskScore(base),
        },
        current: {
          blastRadius: curr.blastRadius,
          timeToCrownSec: curr.timeToCrownSec,
          riskScore: computeRiskScore(curr),
        },
      };
    },
  };
});
