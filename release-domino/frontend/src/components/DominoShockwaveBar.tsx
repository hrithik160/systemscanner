import React from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Zap,
  Flame,
  Crown,
  ShieldCheck,
  ShieldAlert,
  Gauge,
  Activity,
  Boxes,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const DominoShockwaveBar: React.FC = () => {
  const {
    graph,
    risk,
    shockwaveStep,
    isShockwavePlaying,
    shockwaveSpeed,
    startShockwave,
    pauseShockwave,
    resetShockwave,
    viewMode,
    toggleViewMode,
  } = useReleaseStore();

  const maxDepth = Math.max(
    ...graph.nodes.map((n) => n.depth ?? 0),
    ...graph.edges.map((e) => e.depth ?? 0),
    2
  );

  const impactedCount = graph.nodes.filter(
    (n) => n.status === 'impacted' || n.status === 'changed' || n.status === 'failing'
  ).length;

  const crownNodes = graph.nodes.filter((n) => n.is_crown_jewel);
  const crownAtRisk = crownNodes.some(
    (n) => n.status === 'impacted' || n.status === 'failing' || n.risk >= 70
  );

  return (
    <div className="fixed bottom-14 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 px-4 py-2 rounded-2xl bg-slate-950/90 border border-slate-700/80 backdrop-blur-xl shadow-[0_15px_40px_rgba(0,0,0,0.7)] text-xs font-sans">
      {/* 1. Play / Pause / Reset Controls */}
      <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
        {!isShockwavePlaying ? (
          <button
            onClick={() => startShockwave(shockwaveSpeed || 1)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider bg-gradient-to-r from-rose-600 via-pink-600 to-rose-500 hover:brightness-110 text-white shadow-[0_0_15px_rgba(244,63,94,0.4)] transition cursor-pointer"
            title="Simulate failure cascade shockwave along dependency paths"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Simulate Cascade</span>
          </button>
        ) : (
          <button
            onClick={pauseShockwave}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-[0_0_12px_rgba(251,191,36,0.4)] transition cursor-pointer"
            title="Pause cascade animation"
          >
            <Pause className="w-3.5 h-3.5 fill-slate-950" />
            <span>Pause</span>
          </button>
        )}

        <button
          onClick={resetShockwave}
          className="p-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-white transition cursor-pointer"
          title="Reset Shockwave Animation"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 2. Speed Scrubber */}
      <div className="flex items-center gap-1 pr-3 border-r border-slate-800 text-[11px] font-mono">
        <span className="text-slate-400 text-[10px] mr-1">SPEED:</span>
        {[0.5, 1, 2].map((s) => (
          <button
            key={s}
            onClick={() => startShockwave(s)}
            className={`px-2 py-0.5 rounded-lg transition ${
              shockwaveSpeed === s && isShockwavePlaying
                ? 'bg-rose-500 text-white font-bold'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            {s}x
          </button>
        ))}
      </div>

      {/* 3. Step Progression Indicator */}
      <div className="flex items-center gap-2 pr-3 border-r border-slate-800 text-xs">
        <span className="text-slate-400">Step:</span>
        <div className="flex items-center gap-1">
          {Array.from({ length: maxDepth + 1 }).map((_, stepIdx) => {
            const isActive = shockwaveStep !== null && shockwaveStep >= stepIdx;
            return (
              <span
                key={stepIdx}
                className={`w-2 h-2 rounded-full transition-all ${
                  isActive
                    ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e] scale-125'
                    : 'bg-slate-800'
                }`}
                title={`Domino Step ${stepIdx}`}
              />
            );
          })}
        </div>
        <span className="font-mono text-slate-300 font-bold ml-1">
          {shockwaveStep !== null ? `Wave ${shockwaveStep}` : 'Ready'}
        </span>
      </div>

      {/* 4. Telemetry Badges */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Flame className="w-3.5 h-3.5 text-rose-400" />
          <span className="text-slate-400">Blast Radius:</span>
          <strong className="font-mono text-slate-200">
            {impactedCount} / {graph.nodes.length}
          </strong>
        </div>

        <div className="flex items-center gap-1.5">
          <Crown className={`w-3.5 h-3.5 ${crownAtRisk ? 'text-rose-400' : 'text-amber-400'}`} />
          <span className="text-slate-400">Crown Jewels:</span>
          <strong
            className={`font-mono font-bold ${
              crownAtRisk ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {crownAtRisk ? 'EXPOSED' : 'PROTECTED'}
          </strong>
        </div>
      </div>

      {/* 5. 2D / 3D Quick Toggle */}
      <div className="pl-3 border-l border-slate-800">
        <button
          onClick={toggleViewMode}
          className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-purple-950/60 border border-purple-500/50 hover:bg-purple-900/60 text-purple-300 text-xs font-bold transition shadow cursor-pointer"
          title="Toggle 3D Cyberspace vs 2D Canvas (Shortcut: V)"
        >
          <Boxes className="w-3.5 h-3.5 text-purple-400" />
          <span>{viewMode === '3d' ? '2D View' : '3D View'}</span>
        </button>
      </div>
    </div>
  );
};

export default DominoShockwaveBar;
