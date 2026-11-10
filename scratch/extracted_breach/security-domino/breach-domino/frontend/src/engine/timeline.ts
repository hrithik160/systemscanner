import { GEdge, GNode } from '../../../shared/types';

export function formatHopLog(sourceNode: GNode, targetNode: GNode, edge: GEdge): string {
  const templates: Record<GEdge['protocol'], string> = {
    SSH: `SSH credential pivot from ${sourceNode.label} to ${targetNode.label}`,
    SMB: `SMB lateral movement from ${sourceNode.label} to ${targetNode.label}`,
    Telnet: `Unencrypted Telnet exploit from ${sourceNode.label} to ${targetNode.label}`,
    HTTPS: `HTTPS service exploitation from ${sourceNode.label} to ${targetNode.label}`,
    IAM_Trust: `Assumed IAM Trust role from ${sourceNode.label} into ${targetNode.label}`,
  };
  const base = templates[edge.protocol] || `Lateral movement from ${sourceNode.label} to ${targetNode.label}`;
  if (targetNode.is_decoy) return `[HONEYPOT TRAPPED] ${base} (Attacker diverted into containment vault)`;
  if (targetNode.is_crown_jewel) return `[CRITICAL IMPACT] ${base} (Crown Jewel Database compromised)`;
  return base;
}
