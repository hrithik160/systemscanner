import React from 'react';
import { ShieldAlert, Clock, Terminal, SkipForward, RotateCcw, Crosshair, ArrowRight, Shield } from 'lucide-react';
import { useGraphStore } from '../store/graphStore';

export const Hud: React.FC = () => {
  const { sim, baselineSim, mode, playbackStep, setPlaybackStep, getActiveGraph } = useGraphStore();
  const graph = getActiveGraph();

  const stepForward = () => {
    if (sim.timeline.length === 0) return;
    if (playbackStep === null) setPlaybackStep(0);
    else if (playbackStep < sim.timeline.length - 1) setPlaybackStep(playbackStep + 1);
    else setPlaybackStep(null);
  };

  // Build human-readable path label (abbreviated node names)
  const pathLabel = (path: string[]) => {
    return path
      .map((id) => {
        const n = graph.nodes.find((n) => n.id === id);
        return n ? n.label.split(' ')[0] : id.replace('node-', '');
      })
      .join(' → ');
  };

  const showComparison = mode === 'whatif' && baselineSim && baselineSim.path.length > 0;
  const baselinePathSame =
    showComparison && baselineSim && JSON.stringify(baselineSim.edgesUsed) === JSON.stringify(sim.edgesUsed);

  return (
    <div className="fixed bottom-5 left-5 z-20 w-[26rem] rounded-2xl bg-[#0e091d]/90 border border-[#8b5cf6]/40 p-4 backdrop-blur-xl shadow-[0_15px_45px_rgba(10,5,25,0.8)] font-sans">
      {/* Top KPI Row */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-3">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldAlert className="w-3.5 h-3.5 text-red-400" /> BLAST RADIUS
          </div>
          <div className="mt-1 text-2xl font-bold font-mono text-slate-100">
            {sim.blastRadius.compromised}
            <span className="text-sm text-slate-500 font-normal"> / {sim.blastRadius.total}</span>
          </div>
        </div>

        <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-3">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Clock className="w-3.5 h-3.5 text-amber-400" /> TIME TO CROWN
          </div>
          <div className="mt-1 text-2xl font-bold font-mono">
            {sim.trappedByDecoy ? (
              <span className="text-emerald-400 text-sm flex items-center gap-1 font-sans font-bold">
                <Crosshair className="w-4 h-4 text-emerald-400" /> TRAPPED IN HONEYPOT
              </span>
            ) : sim.timeToCrownSec !== null ? (
              <span className="text-red-400">{sim.timeToCrownSec}s</span>
            ) : (
              <span className="text-emerald-400 text-sm font-sans font-bold">PROTECTED</span>
            )}
          </div>
        </div>
      </div>

      {/* What-If Route Comparison Panel */}
      {showComparison && (
        <div className="mb-3 rounded-xl bg-[#06030c] border border-[#2d1b54] p-3 space-y-2">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Shield className="w-3 h-3 text-[#a855f7]" /> Route Comparison
          </div>

          {/* Baseline route */}
          <div>
            <div className="text-[9px] text-slate-500 font-mono uppercase mb-0.5">Baseline (unmodified)</div>
            <div className={`text-[10px] font-mono leading-snug ${baselinePathSame ? 'text-slate-300' : 'text-red-300 line-through opacity-60'}`}>
              {baselineSim ? pathLabel(baselineSim.path) : '—'}
            </div>
          </div>

          {/* Arrow */}
          {!baselinePathSame && (
            <div className="flex items-center gap-1 text-[9px] text-amber-400 font-mono">
              <ArrowRight className="w-3 h-3" /> rerouted via
            </div>
          )}

          {/* Current (what-if) route */}
          {!baselinePathSame && (
            <div>
              <div className="text-[9px] text-slate-500 font-mono uppercase mb-0.5">Active (what-if)</div>
              <div className={`text-[10px] font-mono leading-snug ${
                sim.trappedByDecoy
                  ? 'text-emerald-300'
                  : sim.reachedCrownJewel
                  ? 'text-red-300'
                  : 'text-sky-300'
              }`}>
                {sim.path.length > 0 ? pathLabel(sim.path) : 'No viable path'}
              </div>
            </div>
          )}

          {/* Outcome badge */}
          <div className={`text-[10px] font-bold font-mono px-2 py-1 rounded-lg border mt-1 ${
            sim.trappedByDecoy
              ? 'bg-emerald-950/60 border-emerald-600 text-emerald-300'
              : sim.reachedCrownJewel
              ? 'bg-red-950/60 border-red-600 text-red-300'
              : 'bg-sky-950/60 border-sky-600 text-sky-300'
          }`}>
            {sim.routeStatus === 'trapped_in_decoy'
              ? '🎯 ATTACKER TRAPPED — Crown Jewel protected'
              : sim.routeStatus === 'blocked'
              ? '🛡️ ALL PATHS CUT — Crown Jewel isolated'
              : sim.routeStatus === 'rerouted'
              ? '⚠️ REROUTED — Attacker found alternative path'
              : sim.routeStatus === 'no_entry'
              ? '✅ NO ENTRY — All ingress patched'
              : '🔴 CROWN BREACHED — Deploy defenses'}
          </div>

          {/* Stop reason */}
          <div className="text-[9px] text-slate-400 font-sans leading-snug">
            {sim.stopReason}
          </div>
        </div>
      )}

      {/* Kill-Chain Log Header + What-If Step Controller */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
          <Terminal className="w-3.5 h-3.5 text-[#a855f7]" /> Kill-Chain Narrative
        </div>
        {mode === 'whatif' && sim.timeline.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={stepForward}
              className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-[11px] text-[#c4b5fd] border border-[#8b5cf6]/30 transition"
            >
              <SkipForward className="w-3 h-3" /> Step ({playbackStep === null ? 'All' : playbackStep + 1}/{sim.timeline.length})
            </button>
            {playbackStep !== null && (
              <button
                onClick={() => setPlaybackStep(null)}
                className="p-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-slate-400 border border-[#8b5cf6]/30"
              >
                <RotateCcw className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Narrative Feed */}
      <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1 font-mono text-[11px]">
        {sim.timeline.length === 0 ? (
          <div className="text-slate-500 py-3 text-center">No active attack path detected.</div>
        ) : (
          sim.timeline.map((tick, idx) => {
            const isDimmed = playbackStep !== null && idx > playbackStep;
            const isDecoyEvent = tick.log.includes('[DECOY CONTAINED]');
            const isCrownEvent = tick.log.includes('[CRITICAL IMPACT]');
            return (
              <div
                key={`${tick.nodeId}-${idx}`}
                className={`p-2 rounded-xl border transition ${
                  isDimmed
                    ? 'opacity-25 bg-[#06030c] border-[#1b1035]'
                    : isDecoyEvent
                    ? 'bg-emerald-950/40 border-emerald-700/50 text-emerald-200'
                    : isCrownEvent
                    ? 'bg-red-950/40 border-red-700/50 text-red-200'
                    : 'bg-[#06030c]/90 border-[#2d1b54] text-slate-200'
                }`}
              >
                <span className="text-[#a855f7] font-bold mr-2">[+{tick.t}s]</span>
                <span>{tick.log}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default Hud;
