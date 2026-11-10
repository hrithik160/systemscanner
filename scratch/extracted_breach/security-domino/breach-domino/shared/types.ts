export type NodeType = 'IoT' | 'Workstation' | 'Server' | 'IAM' | 'Database' | 'Decoy';

export interface GNode {
  id: string;
  label: string;
  type: NodeType;
  cvss_score: number;        // 0-10
  vulnerabilities: string[]; // CVE ids
  is_crown_jewel: boolean;
  is_decoy?: boolean;
  status: 'secure' | 'compromised' | 'isolated';
  refs?: { ip?: string; hostname?: string; cloud_id?: string };
  pos?: { x: number; y: number };
  lastSource?: 'cloud' | 'ws' | 'siem' | 'replay';
}

export interface GEdge {
  id: string;
  source: string;
  target: string;
  protocol: 'SSH' | 'HTTPS' | 'SMB' | 'IAM_Trust' | 'Telnet';
  exploit_time_sec: number;
  status: 'open' | 'active_attack' | 'firewalled';
}

export interface Graph {
  nodes: GNode[];
  edges: GEdge[];
}

export interface GraphEvent {
  type:
    | 'node_added'
    | 'node_removed'
    | 'node_updated'
    | 'edge_added'
    | 'edge_removed'
    | 'edge_updated'
    | 'node_compromised'
    | 'cve_found'
    | 'edge_active_attack';
  id: string;
  payload?: Partial<GNode> | Partial<GEdge>;
  ts: number;
  source: 'cloud' | 'ws' | 'siem' | 'replay';
}

export type ServerToClientMsg =
  | { kind: 'snapshot'; graph: Graph }
  | { kind: 'event'; event: GraphEvent };

export interface ReplayControlMsg {
  kind: 'replay_control';
  action: 'start' | 'pause' | 'reset';
  speed?: number;
}

export interface Tick {
  t: number;
  nodeId: string;
  viaEdge: string | null;
  log: string;
}

export type SimRouteStatus =
  | 'optimal'
  | 'rerouted'
  | 'trapped_in_decoy'
  | 'blocked'
  | 'no_entry';

export interface SimResult {
  reachedCrownJewel: boolean;
  trappedByDecoy?: boolean;
  path: string[];
  edgesUsed: string[];
  timeline: Tick[];
  blastRadius: { compromised: number; total: number };
  timeToCrownSec: number | null;
  /** Human-readable explanation of why the simulation ended this way */
  stopReason: string;
  /** Machine-readable outcome classification */
  routeStatus: SimRouteStatus;
};
  timeToCrownSec: number | null;
}

export interface ScorecardComparison {
  baseline: {
    blastRadius: { compromised: number; total: number };
    timeToCrownSec: number | null;
    riskScore: number;
  };
  current: {
    blastRadius: { compromised: number; total: number };
    timeToCrownSec: number | null;
    riskScore: number;
  };
}