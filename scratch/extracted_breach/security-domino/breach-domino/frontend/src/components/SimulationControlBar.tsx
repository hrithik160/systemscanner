import React from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Repeat,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Crosshair,
  ArrowRight,
  Flame,
  Zap,
  Info,
} from 'lucide-react';
import { useGraphStore } from '../store/graphStore';

export const SimulationControlBar: React.FC = () => {
  const {
    simPlayback,
    sim,
    baselineSim,
    mode,
    startSimulation,
    pauseSimulation,
    resumeSimulation,
    resetSimulation,
    replaySimulation,
    setSimSpeed,
    getActiveGraph,
  } = useGraphStore();

  const isRunning = simPlayback.status === 'running';
  const isPaused = simPlayback.status === 'paused';
  const isTrapped = simPlayback.status === 'trapped';
  const isCompleted = simPlayback.status === 'completed';
  const isBlocked = simPlayback.status === 'blocked';
  const isIdle = simPlayback.status === 'idle';

  const graph = getActiveGraph();
  const currentTargetNode = simPlayback.targetNodeId
    ? graph.nodes.find((n) => n.id === simPlayback.targetNodeId)
    : null;

  const lastCompromisedId =
    simPlayback.revealedNodes[simPlayback.revealedNodes.length - 1] || null;
  const lastCompromisedNode = lastCompromisedId
    ? graph.nodes.find((n) => n.id === lastCompromisedId)
    : null;

  // Show reroute indicator when in what-if and route changed
  const wasRerouted =
    mode === 'whatif' &&
    baselineSim &&
    sim.path.length > 0 &&
    JSON.stringify(baselineSim.edgesUsed) !== JSON.stringify(sim.edgesUsed);

  return (
    <div className="flex flex-col px-4 py-2 bg-[#0e091d]/95 border-b border-[#2d1b54] backdrop-blur-xl text-xs font-sans">
      <div className="flex items-center justify-between">
        {/* Left: Playback Controls */}
        <div className="flex items-center gap-2">
          {/* RUN / PAUSE / RESUME Button */}
          {isIdle || isCompleted || isTrapped || isBlocked ? (
            <button
              onClick={startSimulation}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-extrabold uppercase tracking-wider bg-gradient-to-r from-red-600 via-rose-600 to-red-500 hover:from-red-500 hover:to-rose-400 text-white shadow-[0_0_20px_rgba(239,68,68,0.5)] transition group cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-white group-hover:scale-110 transition-transform" />
              <span>RUN LIVE ATTACK</span>
            </button>
          ) : isRunning ? (
            <button
              onClick={pauseSimulation}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-extrabold uppercase tracking-wider bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-[0_0_15px_rgba(251,191,36,0.5)] transition cursor-pointer"
            >
              <Pause className="w-3.5 h-3.5 fill-slate-950" />
              <span>PAUSE</span>
            </button>
          ) : (
            <button
              onClick={resumeSimulation}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-extrabold uppercase tracking-wider bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-[0_0_15px_rgba(16,185,129,0.5)] transition cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-slate-950" />
              <span>RESUME</span>
            </button>
          )}

          {/* Reset Button */}
          <button
            onClick={resetSimulation}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition cursor-pointer"
            title="Reset simulation to initial clean topology"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
            <span>Reset</span>
          </button>

          {/* Replay Button */}
          <button
            onClick={replaySimulation}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition cursor-pointer"
            title="Replay deterministic attack propagation from start"
          >
            <Repeat className="w-3.5 h-3.5 text-[#a855f7]" />
            <span>Replay</span>
          </button>

          {/* Speed Multiplier */}
          <div className="flex items-center ml-1 p-0.5 rounded-lg bg-[#06030c] border border-[#2d1b54]">
            {[1, 2, 4].map((spd) => (
              <button
                key={spd}
                onClick={() => setSimSpeed(spd)}
                className={`px-2 py-0.5 rounded-md font-mono text-[10px] font-bold transition cursor-pointer ${
                  simPlayback.speed === spd
                    ? 'bg-[#8b5cf6] text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Center: Real-Time Progression Feed */}
        <div className="flex items-center gap-4 flex-1 max-w-xl mx-4">
          {/* Status Pill */}
          <div
            className={`px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold tracking-wider uppercase border flex items-center gap-1.5 shrink-0 ${
              isTrapped
                ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                : isCompleted
                ? 'bg-red-950/80 border-red-500 text-red-300 shadow-[0_0_12px_rgba(239,68,68,0.3)]'
                : isBlocked
                ? 'bg-sky-950/80 border-sky-500 text-sky-300'
                : isRunning
                ? 'bg-rose-950/80 border-rose-500 text-rose-200 animate-pulse'
                : isPaused
                ? 'bg-amber-950/80 border-amber-500 text-amber-200'
                : 'bg-[#1b1035] border-[#8b5cf6]/40 text-[#c4b5fd]'
            }`}
          >
            {isTrapped ? (
              <>
                <Crosshair className="w-3 h-3 text-emerald-400" /> TRAPPED IN DECOY
              </>
            ) : isCompleted ? (
              <>
                <Flame className="w-3 h-3 text-red-400" /> CROWN COMPROMISED
              </>
            ) : isBlocked ? (
              <>
                <ShieldCheck className="w-3 h-3 text-sky-400" /> ATTACK BLOCKED
              </>
            ) : isRunning ? (
              <>
                <Zap className="w-3 h-3 text-rose-400 animate-spin" /> INFILTRATING
              </>
            ) : isPaused ? (
              <span>PAUSED</span>
            ) : (
              <>
                <Radio className="w-3 h-3 text-[#a855f7]" /> ARMED // STANDBY
              </>
            )}
          </div>

          {/* Narrative & Infiltration Path Tracker */}
          <div className="flex-1 min-w-0">
            <div className="text-[11px] text-slate-300 truncate font-mono">
              {isRunning && lastCompromisedNode && currentTargetNode ? (
                <span className="flex items-center gap-1.5 text-rose-300">
                  <span className="font-bold text-white">{lastCompromisedNode.label}</span>
                  <ArrowRight className="w-3 h-3 text-rose-400 shrink-0" />
                  <span className="font-bold text-amber-300">{currentTargetNode.label}</span>
                </span>
              ) : (isCompleted || isTrapped || isBlocked) && sim.stopReason ? (
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Info className="w-3 h-3 shrink-0" />
                  <span className="truncate">{sim.stopReason}</span>
                </span>
              ) : (
                <span>{simPlayback.statusMessage}</span>
              )}
            </div>

            {/* Progress Track */}
            <div className="mt-1 w-full h-1 bg-[#1b1035] rounded-full overflow-hidden border border-[#8b5cf6]/20">
              <div
                className={`h-full transition-all duration-300 ${
                  isTrapped
                    ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]'
                    : isCompleted
                    ? 'bg-red-500 shadow-[0_0_8px_#ef4444]'
                    : 'bg-gradient-to-r from-[#8b5cf6] to-rose-500'
                }`}
                style={{ width: `${simPlayback.progressPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* Right: Hop Counter Metric */}
        <div className="flex items-center gap-3 font-mono text-[11px] text-slate-400 shrink-0">
          <div>
            HOP:{' '}
            <span className="font-bold text-white">
              {simPlayback.currentHop < 0 ? 0 : simPlayback.currentHop + 1}
            </span>
            <span className="text-slate-500"> / {sim.path.length || 0}</span>
          </div>
          <div>
            EXPLOIT TIME:{' '}
            <span className="font-bold text-[#c4b5fd]">
              {sim.timeToCrownSec !== null ? `${sim.timeToCrownSec}s` : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Reroute Alert Banner — appears below main bar when attack was rerouted in What-If */}
      {wasRerouted && (
        <div className="mt-1.5 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-950/40 border border-amber-600/50 text-amber-200 text-[10px] font-mono">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>
            <span className="font-bold">ROUTE CHANGE DETECTED: </span>
            {sim.trappedByDecoy
              ? 'Attacker diverted into honeypot — Crown Jewel protected.'
              : sim.reachedCrownJewel
              ? 'Attacker found alternative route to Crown Jewel. Additional defenses required.'
              : 'All routes to Crown Jewel successfully blocked.'}
          </span>
        </div>
      )}
    </div>
  );
};

export default SimulationControlBar;
