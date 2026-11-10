import React from 'react';
import { X, Scissors, ShieldCheck, ArrowRight, ShieldAlert, Zap, Clock } from 'lucide-react';
import { useGraphStore } from '../store/graphStore';

export const EdgeInspector: React.FC = () => {
  const { selectedEdgeId, selectEdge, getActiveGraph, firewallEdge, sim } = useGraphStore();
  if (!selectedEdgeId) return null;

  const graph = getActiveGraph();
  const edge = graph.edges.find((e) => e.id === selectedEdgeId);
  if (!edge) return null;

  const sourceNode = graph.nodes.find((n) => n.id === edge.source);
  const targetNode = graph.nodes.find((n) => n.id === edge.target);

  const isFirewalled = edge.status === 'firewalled';
  const isOnSimPath = sim.edgesUsed.includes(edge.id);

  return (
    <div className="fixed top-20 right-5 z-30 w-84 rounded-2xl bg-[#0e091d]/95 border border-[#8b5cf6]/40 p-5 backdrop-blur-xl shadow-[0_15px_50px_rgba(10,5,25,0.85)] font-sans">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-[#2d1b54] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-[#8b5cf6]/20 text-[#c4b5fd] border border-[#8b5cf6]/40 font-bold">
              NETWORK CONDUIT
            </span>
            {isOnSimPath && (
              <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 font-bold animate-pulse">
                KILL-CHAIN VECTOR
              </span>
            )}
          </div>
          <h3 className="mt-1.5 text-base font-bold text-slate-100 flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#a855f7]" />
            <span>{edge.protocol} Pathway</span>
          </h3>
          <p className="text-xs font-mono text-slate-400">{edge.id}</p>
        </div>
        <button
          onClick={() => selectEdge(null)}
          className="p-1 rounded-lg text-slate-400 hover:bg-[#1f1338] hover:text-slate-100 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Pathway Traversal (Source -> Target) */}
      <div className="mt-4 p-3 rounded-xl bg-[#06030c] border border-[#2d1b54] space-y-2">
        <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
          CONNECTED INFRASTRUCTURE
        </div>
        <div className="flex items-center justify-between text-xs">
          <div className="flex-1 min-w-0">
            <div className="text-[10px] text-slate-400">SOURCE</div>
            <div className="font-semibold text-slate-200 truncate">{sourceNode?.label || edge.source}</div>
            <div className="text-[10px] font-mono text-[#a855f7]">{sourceNode?.type || 'Node'}</div>
          </div>
          <div className="px-2 text-slate-500">
            <ArrowRight className="w-4 h-4 text-[#8b5cf6]" />
          </div>
          <div className="flex-1 min-w-0 text-right">
            <div className="text-[10px] text-slate-400">TARGET</div>
            <div className="font-semibold text-slate-200 truncate">{targetNode?.label || edge.target}</div>
            <div className="text-[10px] font-mono text-[#a855f7]">{targetNode?.type || 'Node'}</div>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="p-2.5 rounded-xl bg-[#06030c] border border-[#2d1b54]">
          <div className="text-[10px] text-slate-400 flex items-center gap-1 font-sans">
            <Clock className="w-3 h-3 text-amber-400" /> EXPLOIT TIME
          </div>
          <div className="mt-1 font-bold text-slate-100 text-sm">
            {edge.exploit_time_sec}s
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-[#06030c] border border-[#2d1b54]">
          <div className="text-[10px] text-slate-400 font-sans">STATUS</div>
          <div className="mt-1 font-bold text-sm">
            {isFirewalled ? (
              <span className="text-red-400 flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" /> BLOCKED
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> OPEN
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Defense Action Button */}
      <div className="mt-4 pt-3 border-t border-[#2d1b54]">
        <button
          onClick={() => firewallEdge(edge.id)}
          className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold tracking-wider uppercase transition flex items-center justify-center gap-2 shadow-lg ${
            isFirewalled
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/40'
              : 'bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white shadow-red-900/40'
          }`}
        >
          {isFirewalled ? (
            <>
              <ShieldCheck className="w-4 h-4" />
              <span>RESTORE CONNECTION</span>
            </>
          ) : (
            <>
              <Scissors className="w-4 h-4" />
              <span>CUT EDGE // FIREWALL</span>
            </>
          )}
        </button>
        <p className="mt-1.5 text-[10px] text-slate-400 text-center">
          {isFirewalled
            ? 'Connection blocked. Attacker cannot pivot through this edge.'
            : 'Severing this connection prevents lateral movement between assets.'}
        </p>
      </div>
    </div>
  );
};

export default EdgeInspector;
