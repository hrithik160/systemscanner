import React from 'react';
import { X, ShieldCheck, ArrowRight, Award } from 'lucide-react';
import { useGraphStore } from '../store/graphStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const Scorecard: React.FC<Props> = ({ open, onClose }) => {
  const { getScorecard } = useGraphStore();
  if (!open) return null;

  const { baseline, current } = getScorecard();
  const riskReduced = baseline.riskScore - current.riskScore;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md">
      <div className="w-full max-w-lg rounded-3xl bg-[#0e091d] border border-[#8b5cf6]/50 p-6 shadow-[0_25px_80px_rgba(10,5,25,0.95)] font-sans">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#2d1b54] pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/20 border border-emerald-500/40">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100">Remediation Scorecard</h2>
              <p className="text-xs text-slate-400">Baseline attack telemetry vs. What-If defenses</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#1b1035] transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Comparison Grid */}
        <div className="mt-6 grid grid-cols-3 items-center gap-4 text-center">
          {/* Baseline */}
          <div className="rounded-2xl bg-red-950/30 border border-red-800/40 p-4">
            <div className="text-[10px] uppercase text-red-300 font-bold tracking-wider">Before (Baseline)</div>
            <div className="mt-3 text-2xl font-mono font-bold text-red-400">
              {baseline.blastRadius.compromised}/{baseline.blastRadius.total}
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Blast Radius</div>

            <div className="mt-3 text-lg font-mono font-semibold text-slate-200">
              {baseline.timeToCrownSec !== null ? `${baseline.timeToCrownSec}s` : 'Safe'}
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Time to Crown</div>

            <div className="mt-3 text-xl font-mono font-bold text-red-400">
              {baseline.riskScore}/100
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Risk Score</div>
          </div>

          {/* Transition Arrow */}
          <div className="flex flex-col items-center justify-center text-slate-500">
            <ArrowRight className="w-8 h-8 text-emerald-400 animate-pulse" />
            <span className="text-[10px] font-mono mt-1 text-emerald-400 font-bold">
              {riskReduced > 0 ? `-${riskReduced} PTS` : 'STABLE'}
            </span>
          </div>

          {/* After Defenses */}
          <div className="rounded-2xl bg-emerald-950/30 border border-emerald-600/40 p-4">
            <div className="text-[10px] uppercase text-emerald-300 font-bold tracking-wider">After Defenses</div>
            <div className="mt-3 text-2xl font-mono font-bold text-emerald-400">
              {current.blastRadius.compromised}/{current.blastRadius.total}
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Blast Radius</div>

            <div className="mt-3 text-lg font-mono font-semibold text-slate-200">
              {current.timeToCrownSec !== null ? `${current.timeToCrownSec}s` : 'BLOCKED'}
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Time to Crown</div>

            <div className="mt-3 text-xl font-mono font-bold text-emerald-400">
              {current.riskScore}/100
            </div>
            <div className="text-[10px] text-slate-400 font-sans mt-0.5">Risk Score</div>
          </div>
        </div>

        {/* Defense Summary Callout */}
        <div className="mt-6 p-3 rounded-2xl bg-[#06030c] border border-[#2d1b54] flex items-center gap-3">
          <Award className="w-5 h-5 text-amber-400 shrink-0" />
          <div className="text-xs text-slate-300">
            {current.timeToCrownSec === null ? (
              <span className="text-emerald-300 font-semibold">
                Critical attack chain neutralized. Crown jewel completely isolated from lateral movement.
              </span>
            ) : (
              <span>
                Risk score improved by <strong className="text-emerald-400">{riskReduced} points</strong>. Further isolate IAM/DB edges to block crown breach.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Scorecard;
