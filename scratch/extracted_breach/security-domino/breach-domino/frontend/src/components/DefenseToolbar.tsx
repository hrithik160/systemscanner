import React from 'react';
import {
  Scissors,
  ShieldPlus,
  Crosshair,
  Play,
  Pause,
  RotateCcw,
  FastForward,
  BarChart3,
  Radio,
  FlaskConical,
  Undo2,
} from 'lucide-react';
import { useGraphStore } from '../store/graphStore';
import { socketClient } from '../store/socket';

interface Props {
  onOpenScorecard: () => void;
}

export const DefenseToolbar: React.FC<Props> = ({ onOpenScorecard }) => {
  const {
    mode,
    setMode,
    activeTool,
    setActiveTool,
    deployDecoy,
    resetWhatIf,
    connected,
  } = useGraphStore();

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center gap-2">
      {/* Sandbox What-If Banner */}
      {mode === 'whatif' && (
        <div className="px-4 py-1 rounded-full bg-[#8b5cf6]/20 border border-[#8b5cf6]/50 text-[#c4b5fd] text-xs font-semibold tracking-wide flex items-center gap-2 shadow-lg backdrop-blur-md">
          <FlaskConical className="w-3.5 h-3.5 text-[#a855f7]" />
          <span>WHAT-IF DEFENSE LAB // Live telemetry safe • Stress-testing active</span>
        </div>
      )}

      <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-[#0e091d]/90 border border-[#8b5cf6]/40 backdrop-blur-xl shadow-[0_15px_40px_rgba(10,5,25,0.7)]">
        {/* Connection Status Dot */}
        <div className="flex items-center gap-2 pr-3 border-r border-[#2d1b54]">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              connected ? 'bg-emerald-400 shadow-[0_0_10px_#10b981]' : 'bg-red-500 animate-pulse'
            }`}
          />
          <span className="text-xs font-mono text-slate-300">
            {connected ? 'WS LIVE' : 'DEMO'}
          </span>
        </div>

        {/* Live vs What-If Mode Switch */}
        <div className="flex rounded-xl bg-[#06030c] p-1 border border-[#2d1b54]">
          <button
            onClick={() => setMode('live')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
              mode === 'live'
                ? 'bg-gradient-to-r from-red-600 to-rose-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Radio className="w-3.5 h-3.5" /> Live Stream
          </button>
          <button
            onClick={() => setMode('whatif')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
              mode === 'whatif'
                ? 'bg-gradient-to-r from-[#8b5cf6] to-[#7c3aed] text-white font-semibold shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5" /> What-If Lab
          </button>
        </div>

        {/* Mode-Specific Actions */}
        {mode === 'live' ? (
          /* Live Mode: Replay Controls */
          <div className="flex items-center gap-1.5 pl-2 border-l border-[#2d1b54]">
            <button
              onClick={() => socketClient.sendReplayControl('start', 1)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-xs text-slate-200 border border-[#8b5cf6]/30 transition"
              title="Start Replay (1x)"
            >
              <Play className="w-3.5 h-3.5 text-emerald-400" /> 1x
            </button>
            <button
              onClick={() => socketClient.sendReplayControl('start', 2)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-xs text-slate-200 border border-[#8b5cf6]/30 transition"
              title="Fast Replay (2x)"
            >
              <FastForward className="w-3.5 h-3.5 text-[#a855f7]" /> 2x
            </button>
            <button
              onClick={() => socketClient.sendReplayControl('pause')}
              className="p-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-slate-200 border border-[#8b5cf6]/30 transition"
              title="Pause Replay"
            >
              <Pause className="w-3.5 h-3.5 text-amber-400" />
            </button>
            <button
              onClick={() => socketClient.sendReplayControl('reset')}
              className="p-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] text-slate-200 border border-[#8b5cf6]/30 transition"
              title="Reset Topology"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
            </button>
          </div>
        ) : (
          /* What-If Mode: Remediation Arsenal */
          <div className="flex items-center gap-2 pl-2 border-l border-[#2d1b54]">
            <button
              onClick={() => setActiveTool(activeTool === 'scissors' ? 'select' : 'scissors')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                activeTool === 'scissors'
                  ? 'bg-red-500/25 border-red-400 text-red-200 shadow-[0_0_12px_rgba(239,68,68,0.4)]'
                  : 'bg-[#1b1035] border-[#8b5cf6]/30 text-slate-200 hover:bg-[#28164f]'
              }`}
              title="Toggle Cut Edge Mode: Click any 3D connection to firewall it"
            >
              <Scissors className="w-3.5 h-3.5 text-red-400" />
              <span>Cut Edge</span>
            </button>

            <button
              onClick={() => setActiveTool(activeTool === 'patch' ? 'select' : 'patch')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                activeTool === 'patch'
                  ? 'bg-emerald-500/25 border-emerald-400 text-emerald-200 shadow-[0_0_12px_rgba(16,185,129,0.4)]'
                  : 'bg-[#1b1035] border-[#8b5cf6]/30 text-slate-200 hover:bg-[#28164f]'
              }`}
              title="Toggle Patch Mode: Click any 3D asset to remediate CVEs"
            >
              <ShieldPlus className="w-3.5 h-3.5 text-emerald-400" />
              <span>Patch Node</span>
            </button>

            <button
              onClick={deployDecoy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#10b981]/20 border border-[#10b981]/40 text-emerald-300 hover:bg-[#10b981]/30 transition"
              title="Deploy decoy honeypot vault to divert attacker lateral movement"
            >
              <Crosshair className="w-3.5 h-3.5 text-emerald-400" />
              <span>Drop Decoy</span>
            </button>

            <button
              onClick={resetWhatIf}
              className="p-1.5 rounded-xl bg-[#1b1035] hover:bg-[#28164f] text-slate-400 hover:text-slate-200 border border-[#8b5cf6]/30 transition"
              title="Reset What-If Sandbox to baseline"
            >
              <Undo2 className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={onOpenScorecard}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-[#8b5cf6] to-[#6d28d9] hover:from-[#7c3aed] hover:to-[#5b21b6] text-white shadow-lg transition"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Scorecard</span>
            </button>
          </div>
        )}
      </div>

      {/* Active Defense Tool Indicator */}
      {mode === 'whatif' && activeTool !== 'select' && (
        <div className="px-3 py-0.5 rounded-lg bg-[#06030c]/90 border border-[#8b5cf6]/50 text-[10px] font-mono text-[#c4b5fd] animate-pulse">
          {activeTool === 'scissors'
            ? '✂️ CUT TOOL ACTIVE: Click any network connection in 3D to firewall it'
            : '🛡️ PATCH TOOL ACTIVE: Click any infrastructure asset in 3D to patch it'}
        </div>
      )}
    </div>
  );
};

export default DefenseToolbar;
