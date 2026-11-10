import React from 'react';
import { X, ShieldAlert, ShieldCheck, Network, Cpu, ShieldPlus, Crown, Crosshair } from 'lucide-react';
import { useGraphStore } from '../store/graphStore';

export const NodeInspector: React.FC = () => {
  const { selectedNodeId, selectNode, getActiveGraph, patchNode, sim } = useGraphStore();
  if (!selectedNodeId) return null;

  const graph = getActiveGraph();
  const node = graph.nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  const connectedEdges = graph.edges.filter(
    (e) => e.source === node.id || e.target === node.id
  );

  const isPatched = node.vulnerabilities.length === 0 && node.cvss_score <= 1.0 && !node.is_crown_jewel && !node.is_decoy;
  const isCompromised = node.status === 'compromised';
  const isOnSimPath = sim.path.includes(node.id);

  return (
    <div className="fixed top-20 right-5 z-30 w-84 rounded-2xl bg-[#0e091d]/95 border border-[#8b5cf6]/40 p-5 backdrop-blur-xl shadow-[0_15px_50px_rgba(10,5,25,0.85)] font-sans">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-[#2d1b54] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-[#8b5cf6]/20 text-[#c4b5fd] border border-[#8b5cf6]/40 font-bold">
              {node.type}
            </span>
            {node.is_crown_jewel && (
              <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold flex items-center gap-1">
                <Crown className="w-3 h-3 text-amber-400" /> CROWN JEWEL
              </span>
            )}
            {node.is_decoy && (
              <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold flex items-center gap-1">
                <Crosshair className="w-3 h-3 text-emerald-400" /> HONEYPOT
              </span>
            )}
            {isOnSimPath && (
              <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 font-bold animate-pulse">
                IN ATTACK CHAIN
              </span>
            )}
          </div>
          <h3 className="mt-1.5 text-base font-bold text-slate-100">{node.label}</h3>
          <p className="text-xs font-mono text-slate-400">{node.id}</p>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="p-1 rounded-lg text-slate-400 hover:bg-[#1f1338] hover:text-slate-100 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Asset Status Badge */}
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-400">Security Status:</span>
        <span
          className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] uppercase border ${
            isCompromised
              ? 'bg-red-950/80 text-red-400 border-red-500/50 shadow-[0_0_10px_rgba(239,68,68,0.3)] animate-pulse'
              : isPatched
              ? 'bg-emerald-950/80 text-emerald-400 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
              : 'bg-[#1b1035] text-[#c4b5fd] border-[#8b5cf6]/40'
          }`}
        >
          {isCompromised ? 'COMPROMISED' : isPatched ? 'PROTECTED / PATCHED' : node.status.toUpperCase()}
        </span>
      </div>

      {/* Asset Identifiers */}
      <div className="mt-3 space-y-1 rounded-xl bg-[#06030c] p-3 border border-[#2d1b54] text-xs font-mono">
        <div className="flex items-center gap-1.5 text-slate-400 font-sans font-semibold mb-1">
          <Cpu className="w-3.5 h-3.5 text-[#a855f7]" /> Asset Telemetry
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">IP Address:</span>
          <span className="text-slate-200">{node.refs?.ip || '10.0.x.x'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Hostname:</span>
          <span className="text-slate-200 truncate max-w-[150px]">{node.refs?.hostname || node.id}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">CVSS Risk:</span>
          <span className={`font-bold ${node.cvss_score >= 8 ? 'text-red-400' : node.cvss_score >= 4 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {node.cvss_score.toFixed(1)} / 10.0
          </span>
        </div>
      </div>

      {/* Vulnerabilities Section */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
          <span className="flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            Vulnerabilities ({node.vulnerabilities.length})
          </span>
        </div>

        {node.vulnerabilities.length === 0 ? (
          <div className="text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-2.5 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Zero unpatched vulnerabilities on this asset.</span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {node.vulnerabilities.map((cve) => (
              <span
                key={cve}
                className="px-2 py-0.5 rounded bg-red-500/15 border border-red-500/30 text-red-300 font-mono text-[10px]"
              >
                {cve}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Connected Pathways */}
      <div className="mt-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-1.5">
          <Network className="w-3.5 h-3.5 text-[#a855f7]" /> Lateral Connections ({connectedEdges.length})
        </div>
        <div className="max-h-24 overflow-y-auto space-y-1 text-[10px] font-mono pr-1">
          {connectedEdges.map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between px-2 py-1 rounded bg-[#06030c] border border-[#2d1b54]"
            >
              <span className="truncate text-slate-300">
                {e.source === node.id ? `-> ${e.target}` : `<- ${e.source}`}
              </span>
              <span className={`ml-2 px-1.5 rounded ${e.status === 'firewalled' ? 'text-red-400 line-through' : 'text-[#c4b5fd]'}`}>
                {e.protocol}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Defense Action: Patch Node */}
      {!node.is_crown_jewel && !node.is_decoy && (
        <div className="mt-4 pt-3 border-t border-[#2d1b54]">
          {isPatched ? (
            <div className="w-full py-2 px-3 rounded-xl bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 text-xs font-bold flex items-center justify-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>ASSET SHIELDED & HARDENED</span>
            </div>
          ) : (
            <button
              onClick={() => patchNode(node.id)}
              className="w-full py-2.5 px-4 rounded-xl text-xs font-bold tracking-wider uppercase transition flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-950/50"
            >
              <ShieldPlus className="w-4 h-4" />
              <span>PATCH ASSET // REMEDIATE CVES</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default NodeInspector;
