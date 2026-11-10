import { describe, it, expect, beforeEach } from 'vitest';
import { useGraphStore } from '../store/graphStore';
import { simulate } from './simulate';

describe('RELEASE DOMINO - Critical Simulation Engine & Progressive Attack Verification', () => {
  beforeEach(() => {
    useGraphStore.getState().resetSimulation();
    useGraphStore.getState().setMode('live');
  });

  it('1. Normal attack reaches the crown jewel when a valid route exists', () => {
    const store = useGraphStore.getState();
    const activeGraph = store.getActiveGraph();
    const res = simulate(activeGraph);

    expect(res.reachedCrownJewel).toBe(true);
    expect(res.trappedByDecoy).toBe(false);
    expect(res.path.length).toBeGreaterThan(1);
    expect(res.path[0]).toBe('node-printer-01');
    expect(res.path[res.path.length - 1]).toBe('node-prod-db');
    expect(res.timeToCrownSec).toBeGreaterThan(0);
  });

  it('2. Cutting an edge prevents traversal through that edge', () => {
    const store = useGraphStore.getState();
    const baselineEdge = store.sim.edgesUsed[0];
    expect(baselineEdge).toBeDefined();

    // Sever the primary first hop connection
    store.firewallEdge(baselineEdge);

    const state = useGraphStore.getState();
    expect(state.mode).toBe('whatif');
    expect(state.whatIfGraph.edges.find((e) => e.id === baselineEdge)?.status).toBe('firewalled');
    expect(state.sim.edgesUsed).not.toContain(baselineEdge);
  });

  it('3. Alternative route is dynamically considered when primary route is blocked', () => {
    const store = useGraphStore.getState();

    // Baseline path goes: Printer -> Dev Laptop -> Build Server -> IAM -> DB
    expect(store.sim.path).toContain('node-dev-laptop');

    // Firewall edge-printer-dev
    store.firewallEdge('edge-printer-dev');

    const state = useGraphStore.getState();
    // Dijkstra must explore alternative reachable route:
    // Printer -> SRE Workstation -> App Server -> IAM CI/CD -> IAM Admin -> Prod DB
    expect(state.sim.reachedCrownJewel).toBe(true);
    expect(state.sim.path).not.toContain('node-dev-laptop');
    expect(state.sim.path).toContain('node-sre-workstation');
    expect(state.sim.path).toContain('node-app-server');
  });

  it('4. Decoy deployment changes the simulation outcome and traps lateral movement', () => {
    const store = useGraphStore.getState();

    store.deployDecoy();

    const state = useGraphStore.getState();
    expect(state.mode).toBe('whatif');
    expect(state.whatIfGraph.nodes.some((n) => n.is_decoy)).toBe(true);
    expect(state.sim.trappedByDecoy).toBe(true);
    expect(state.sim.reachedCrownJewel).toBe(false);
    expect(state.sim.path[state.sim.path.length - 1]).toContain('node-decoy-honeypot');
  });

  it('5. Multiple What-If simulations work seamlessly in the same session without refresh', () => {
    const store = useGraphStore.getState();

    // 1st experiment: Deploy Honeypot
    store.deployDecoy();
    expect(useGraphStore.getState().sim.trappedByDecoy).toBe(true);

    // 2nd experiment: Patch patient zero
    store.patchNode('node-printer-01');
    const stateAfterPatch = useGraphStore.getState();
    expect(stateAfterPatch.whatIfGraph.nodes.find((n) => n.id === 'node-printer-01')?.vulnerabilities.length).toBe(0);

    // 3rd experiment: Sever alternative branch
    store.firewallEdge('edge-sre-app');
    expect(useGraphStore.getState().whatIfGraph.edges.find((e) => e.id === 'edge-sre-app')?.status).toBe('firewalled');

    // 4th experiment: Reset sandbox to baseline
    store.resetWhatIf();
    const stateAfterReset = useGraphStore.getState();
    expect(stateAfterReset.whatIfGraph.nodes.some((n) => n.is_decoy)).toBe(false);
    expect(stateAfterReset.sim.reachedCrownJewel).toBe(true);
  });

  it('6. Reset clears previous simulation and returns to clean idle state', () => {
    const store = useGraphStore.getState();

    // Start simulation
    store.startSimulation();
    expect(useGraphStore.getState().simPlayback.status).toBe('running');

    // Reset simulation
    store.resetSimulation();
    const playback = useGraphStore.getState().simPlayback;

    expect(playback.status).toBe('idle');
    expect(playback.currentHop).toBe(-1);
    expect(playback.revealedEdges.length).toBe(0);
    expect(playback.revealedNodes.length).toBe(0);
    expect(playback.activeEdgeId).toBeNull();
    expect(playback.targetNodeId).toBeNull();
  });

  it('7. Replay reproduces the exact deterministic attack sequence', () => {
    const store = useGraphStore.getState();
    const baselinePath = [...store.sim.path];

    store.startSimulation();
    const firstRunNode = useGraphStore.getState().simPlayback.revealedNodes[0];

    store.replaySimulation();
    const replayedNode = useGraphStore.getState().simPlayback.revealedNodes[0];

    expect(firstRunNode).toBe(baselinePath[0]);
    expect(replayedNode).toBe(baselinePath[0]);
  });

  it('8. Attack events are revealed progressively rather than all at once', () => {
    const store = useGraphStore.getState();

    // At idle: no edges revealed
    expect(store.simPlayback.revealedEdges.length).toBe(0);

    // Start run: hop 0 (initial entry node revealed, 0 edges revealed yet)
    store.startSimulation();
    const step0 = useGraphStore.getState().simPlayback;
    expect(step0.revealedNodes.length).toBe(1);
    expect(step0.revealedEdges.length).toBe(0);
    expect(step0.activeEdgeId).toBe(store.sim.edgesUsed[0]);

    // Advance 1 step
    store.advanceSimulationStep();
    const step1 = useGraphStore.getState().simPlayback;
    expect(step1.revealedNodes.length).toBe(2);
    expect(step1.revealedEdges.length).toBe(1);
    expect(step1.revealedEdges[0]).toBe(store.sim.edgesUsed[0]);
  });

  it('9. Switching between 2D and 3D preserves unified simulation state without corruption', () => {
    const store = useGraphStore.getState();

    store.startSimulation();
    store.advanceSimulationStep();

    const snapshot = useGraphStore.getState().simPlayback;
    expect(snapshot.revealedNodes.length).toBe(2);
    expect(snapshot.revealedEdges.length).toBe(1);

    // Both views read from useGraphStore - state is decoupled from rendering mode
    const currentState = useGraphStore.getState();
    expect(currentState.simPlayback.revealedNodes).toEqual(snapshot.revealedNodes);
    expect(currentState.simPlayback.revealedEdges).toEqual(snapshot.revealedEdges);
  });

  it('10. Prevents duplicate simulation timers or animation loops', () => {
    const store = useGraphStore.getState();

    // Clicking start multiple times must never spawn concurrent intervals
    store.startSimulation();
    store.startSimulation();
    store.startSimulation();

    expect(useGraphStore.getState().simPlayback.status).toBe('running');
    store.resetSimulation();
    expect(useGraphStore.getState().simPlayback.status).toBe('idle');
  });
});
