import { Graph, GNode, GEdge, SimResult, Tick, SimRouteStatus } from '../../../shared/types';
import { formatHopLog } from './timeline';

export function simulate(graph: Graph, opts?: { entry?: string[] }): SimResult {
  const nodeMap = new Map<string, GNode>(graph.nodes.map((n) => [n.id, n]));
  const totalNodes = graph.nodes.filter((n) => !n.is_decoy).length;

  // Rule 1: Start set is every node with status 'compromised' (or opts.entry)
  const explicitCompromised = graph.nodes.filter((n) => n.status === 'compromised').map((n) => n.id);
  const startIds = opts?.entry?.length
    ? opts.entry.filter((id) => nodeMap.has(id))
    : explicitCompromised;

  // Fallback entry selection if no node is explicitly marked compromised
  let effectiveStartIds = startIds;

  if (effectiveStartIds.length === 0) {
    const perimeterOrder = ['node-printer-01', 'node-vpn', 'node-monitor'];
    for (const pid of perimeterOrder) {
      const pNode = nodeMap.get(pid);
      if (pNode && pNode.status !== 'isolated' && (pNode.vulnerabilities.length > 0 || pNode.status === 'compromised')) {
        effectiveStartIds = [pid];
        break;
      }
    }

    if (effectiveStartIds.length === 0) {
      const anyVulnerable = graph.nodes.find((n) => !n.is_decoy && n.status !== 'isolated' && n.vulnerabilities.length > 0);
      if (anyVulnerable) {
        effectiveStartIds = [anyVulnerable.id];
      }
    }
  }

  // If literally every asset in the graph is patched or isolated, attack cannot enter
  if (effectiveStartIds.length === 0) {
    return {
      reachedCrownJewel: false,
      trappedByDecoy: false,
      path: [],
      edgesUsed: [],
      timeline: [],
      blastRadius: { compromised: 0, total: totalNodes },
      timeToCrownSec: null,
      routeStatus: 'no_entry',
      stopReason: 'No exploitable ingress point found. All perimeter assets are patched or isolated.',
    };
  }

  // Build adjacency list
  const adj = new Map<string, GEdge[]>();
  for (const edge of graph.edges) {
    if (!adj.has(edge.source)) adj.set(edge.source, []);
    adj.get(edge.source)!.push(edge);
  }

  const dist = new Map<string, number>();
  const prevNode = new Map<string, string | null>();
  const prevEdge = new Map<string, GEdge | null>();
  const visited = new Set<string>();

  for (const id of effectiveStartIds) {
    const n = nodeMap.get(id);
    if (n && n.status !== 'isolated') {
      dist.set(id, 0);
      prevNode.set(id, null);
      prevEdge.set(id, null);
    }
  }

  // Multi-source Dijkstra
  while (true) {
    let u: string | null = null;
    let bestDist = Infinity;

    for (const [id, d] of dist.entries()) {
      if (!visited.has(id) && d < bestDist) {
        bestDist = d;
        u = id;
      }
    }

    if (u === null) break;
    visited.add(u);

    const uNode = nodeMap.get(u)!;
    // If attacker hits a decoy, they are trapped there and do not pivot out of it
    if (uNode.is_decoy) continue;

    for (const edge of adj.get(u) || []) {
      // Rule 2: Firewalled edges are skipped
      if (edge.status === 'firewalled') continue;

      const target = nodeMap.get(edge.target);
      // Rule 2: Isolated nodes are skipped
      if (!target || target.status === 'isolated') continue;

      // Rule 4: Patched node (zero vulnerabilities) cannot be breached via exploit edges (IAM_Trust still operates)
      const isPatched = target.vulnerabilities.length === 0 && !target.is_decoy;
      if (isPatched && edge.protocol !== 'IAM_Trust' && target.status !== 'compromised') {
        continue;
      }

      // Rule 2 & 5: Weight = exploit_time_sec * (10 / max(target.cvss_score, 1))
      const weight =
        target.status === 'compromised'
          ? 0.01
          : Number((edge.exploit_time_sec * (10 / Math.max(target.cvss_score, 1))).toFixed(1));

      const alt = bestDist + weight;
      if (alt < (dist.get(target.id) ?? Infinity)) {
        dist.set(target.id, alt);
        prevNode.set(target.id, u);
        prevEdge.set(target.id, edge);
      }
    }
  }

  // Rule 5: Candidate targets include Crown Jewels AND Decoys that are reachable
  const candidateTargets = graph.nodes.filter(
    (n) => (n.is_crown_jewel || n.is_decoy) && dist.has(n.id)
  );

  let chosenTarget: GNode | null = null;
  let minTargetDist = Infinity;

  for (const t of candidateTargets) {
    const d = dist.get(t.id)!;
    if (d < minTargetDist) {
      minTargetDist = d;
      chosenTarget = t;
    }
  }

  const path: string[] = [];
  const edgesUsed: string[] = [];
  const timeline: Tick[] = [];

  if (chosenTarget) {
    let curr: string | null = chosenTarget.id;
    while (curr !== null) {
      path.unshift(curr);
      const e = prevEdge.get(curr);
      if (e) edgesUsed.unshift(e.id);
      curr = prevNode.get(curr) ?? null;
    }

    for (let i = 0; i < path.length; i++) {
      const nid = path[i];
      const node = nodeMap.get(nid)!;
      const tSec = Math.round(dist.get(nid) || 0);
      if (i === 0) {
        timeline.push({
          t: 0,
          nodeId: nid,
          viaEdge: null,
          log: "Initial breach established on " + node.label + " (" + (node.refs?.ip || node.id) + ")",
        });
      } else {
        const edge = prevEdge.get(nid)!;
        const srcNode = nodeMap.get(path[i - 1])!;
        timeline.push({
          t: tSec,
          nodeId: nid,
          viaEdge: edge.id,
          log: formatHopLog(srcNode, node, edge),
        });
      }
    }

    // If the attacker ends at a decoy, add an explicit containment event
    if (chosenTarget.is_decoy) {
      timeline.push({
        t: Math.round(minTargetDist) + 1,
        nodeId: chosenTarget.id,
        viaEdge: null,
        log: "[DECOY CONTAINED] Attacker isolated in " + chosenTarget.label + ". SecOps tripwire alarmed. Lateral movement to production assets blocked.",
      });
    }
  }

  const reachableNonDecoys = Array.from(visited).filter((id) => !nodeMap.get(id)?.is_decoy);
  const reachedCrown = Boolean(chosenTarget && chosenTarget.is_crown_jewel && !chosenTarget.is_decoy);
  const trappedByDecoy = Boolean(chosenTarget && chosenTarget.is_decoy);

  // Determine routeStatus and stopReason
  let routeStatus: SimRouteStatus;
  let stopReason: string;

  if (reachedCrown) {
    routeStatus = 'optimal';
    stopReason = 'Attacker reached Crown Jewel via ' + path.join(' -> ') + '. Deploy firewalls or patch CVEs on the attack path to break the chain.';
  } else if (trappedByDecoy) {
    routeStatus = 'trapped_in_decoy';
    stopReason = 'Attacker lured into ' + (chosenTarget?.label || 'honeypot') + ' and contained. Production Crown Jewel is protected. SecOps was alerted.';
  } else if (path.length === 0) {
    routeStatus = 'no_entry';
    stopReason = 'No exploitable ingress point found. All perimeter assets are patched or isolated.';
  } else {
    routeStatus = 'blocked';
    stopReason = 'All reachable paths to the Crown Jewel are blocked by firewalls or patched nodes. Crown Jewel is protected.';
  }

  return {
    reachedCrownJewel: reachedCrown,
    trappedByDecoy,
    path,
    edgesUsed,
    timeline,
    blastRadius: {
      compromised: trappedByDecoy
        ? Math.min(path.length - 1, totalNodes)
        : reachedCrown
        ? reachableNonDecoys.length
        : Math.min(path.length, reachableNonDecoys.length),
      total: totalNodes,
    },
    timeToCrownSec: reachedCrown ? Math.round(minTargetDist) : null,
    routeStatus,
    stopReason,
  };
}

export default simulate;
