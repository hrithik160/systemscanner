import { describe, it, expect } from 'vitest';
import { simulate } from './simulate';
import sampleTopology from '../../../shared/topology.sample.json';
import { Graph } from '../../../shared/types';

describe('Attack Simulation Scenarios Check', () => {
  const getBaseGraph = (): Graph => JSON.parse(JSON.stringify(sampleTopology));

  it('Scenario A: Normal baseline attack', () => {
    const g = getBaseGraph();
    const res = simulate(g);
    console.log('Baseline path:', res.path);
    console.log('Baseline edges:', res.edgesUsed);
    console.log('Reached crown:', res.reachedCrownJewel);
    expect(res.reachedCrownJewel).toBe(true);
    expect(res.path[0]).toBe('node-printer-01');
    expect(res.path[res.path.length - 1]).toBe('node-prod-db');
  });

  it('Scenario B: Cut primary edge e-printer-dev', () => {
    const g = getBaseGraph();
    const edge = g.edges.find(e => e.id === 'edge-printer-dev');
    if (edge) edge.status = 'firewalled';
    const res = simulate(g);
    console.log('After cutting edge-printer-dev:', res.path);
    console.log('Reached crown:', res.reachedCrownJewel);
    // Should take alternative route via SRE workstation -> App Server -> IAM -> DB!
    expect(res.reachedCrownJewel).toBe(true);
    expect(res.path).toContain('node-sre-workstation');
  });

  it('Scenario C: Patch node-dev-laptop', () => {
    const g = getBaseGraph();
    const node = g.nodes.find(n => n.id === 'node-dev-laptop');
    if (node) {
      node.vulnerabilities = [];
      node.cvss_score = 0.0;
    }
    const res = simulate(g);
    console.log('After patching dev laptop:', res.path);
    console.log('Reached crown:', res.reachedCrownJewel);
  });

  it('Scenario D: Deploy decoy honeypot', () => {
    const g = getBaseGraph();
    const decoyId = 'node-decoy-honeypot';
    g.nodes.push({
      id: decoyId,
      label: 'Decoy Honeypot Vault',
      type: 'Decoy',
      cvss_score: 10.0,
      vulnerabilities: ['CVE-2024-9999-HONEY'],
      is_crown_jewel: false,
      is_decoy: true,
      status: 'secure',
      refs: { ip: '10.0.50.99', hostname: 'honeypot-vault-prod' },
      pos: { x: 500, y: 560 },
    });
    const attachTargets = ['node-dev-laptop', 'node-printer-01', 'node-build-srv', 'node-sre-workstation'];
    attachTargets.forEach((srcId, idx) => {
      g.edges.push({
        id: `edge-decoy-${idx + 1}`,
        source: srcId,
        target: decoyId,
        protocol: 'SSH',
        exploit_time_sec: 2,
        status: 'open',
      });
    });

    const res = simulate(g);
    console.log('After decoy deployed path:', res.path);
    console.log('Reached crown:', res.reachedCrownJewel);
    console.log('Trapped by decoy:', res.trappedByDecoy);
  });
});
