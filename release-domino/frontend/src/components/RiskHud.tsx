import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Flame,
  GitMerge,
  Crown,
  Layers,
  FileDiff,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const RiskHud: React.FC = () => {
  const {
    graph,
    risk,
    diff,
    merge,
    isShockwavePlaying,
    setActiveInspectorTab,
    runConflictResolver,
  } = useReleaseStore();

  const totalNodes = graph.nodes.length;
  const impactedCount = (risk.impacted || []).length;

  const impactedIds = new Set((risk.impacted || []).map((i) => i.id));
  const crownJewelsHit = graph.nodes.filter((n) => n.is_crown_jewel && impactedIds.has(n.id));

  const verdictConfig =
    risk.verdict === 'GO'
      ? {
          bg: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300',
          bar: 'bg-emerald-500',
          text: 'text-emerald-400',
          icon: ShieldCheck,
        }
      : risk.verdict === 'CAUTION'
      ? {
          bg: 'bg-amber-500/20 border-amber-500/50 text-amber-300',
          bar: 'bg-amber-500',
          text: 'text-amber-400',
          icon: AlertTriangle,
        }
      : {
          bg: 'bg-red-500/25 border-red-500/60 text-red-200',
          bar: 'bg-red-500',
          text: 'text-red-400',
          icon: ShieldAlert,
        };

  const VerdictIcon = verdictConfig.icon;

  return (
    <div className="fixed top-20 left-5 z-30 w-84 rounded-2xl bg-slate-900/95 border border-slate-700/90 p-5 backdrop-blur-md shadow-2xl space-y-4 max-h-[80vh] overflow-y-auto">
      {/* Header Row + Verdict Chip */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Flame className={`w-5 h-5 text-rose-400 ${isShockwavePlaying ? 'animate-bounce' : ''}`} />
          <h2 className="text-sm font-bold tracking-wide uppercase text-slate-100">
            Release Risk HUD
          </h2>
        </div>
        <span
          className={`flex items-center gap-1.5 text-xs font-mono px-3 py-1 rounded-full border font-extrabold ${verdictConfig.bg}`}
        >
          <VerdictIcon className="w-4 h-4" />
          {risk.verdict}
        </span>
      </div>

      {/* Risk Score Gauge (0-100) */}
      <div>
        <div className="flex justify-between items-baseline mb-1.5">
          <span className="text-xs font-medium text-slate-300">Release Risk Score</span>
          <span className={`font-mono font-extrabold text-xl ${verdictConfig.text}`}>
            {Math.round(risk.score)} <span className="text-xs text-slate-400 font-normal">/ 100</span>
          </span>
        </div>
        <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${verdictConfig.bar}`}
            style={{ width: `${Math.min(100, Math.max(4, risk.score))}%` }}
          />
        </div>
        <div className="flex justify-between text-[11px] font-mono text-slate-400 mt-1.5">
          <span>GO &lt;35</span>
          <span>CAUTION 35–65</span>
          <span>HOLD &gt;65</span>
        </div>
      </div>

      {/* Blast Radius & Diff Counter Cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-slate-950/90 p-3 border border-slate-800">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
            <Layers className="w-4 h-4 text-rose-400" />
            <span>Blast Radius</span>
          </div>
          <div className="mt-1.5 text-xl font-mono font-bold text-slate-100">
            {impactedCount}{' '}
            <span className="text-xs text-slate-400 font-normal">/ {totalNodes} nodes</span>
          </div>
          <div className="mt-1 text-xs font-medium">
            {crownJewelsHit.length > 0 ? (
              <span className="flex items-center gap-1 text-amber-300">
                <Crown className="w-3.5 h-3.5" /> {crownJewelsHit.length} Crown Jewel Hit
              </span>
            ) : (
              <span className="text-emerald-400">Crown Jewels Safe</span>
            )}
          </div>
        </div>

        <div
          onClick={() => setActiveInspectorTab('risk')}
          className="rounded-xl bg-slate-950/90 p-3 border border-slate-800 cursor-pointer hover:border-slate-700 transition"
          title="Click to inspect file changes in Risk & Tests tab"
        >
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
            <FileDiff className="w-4 h-4 text-sky-400" />
            <span>Code Changes</span>
          </div>
          <div className="mt-1.5 text-base font-mono font-bold flex items-center gap-1.5">
            <span className="text-emerald-400">+{diff.total_added}</span>
            <span className="text-slate-500">/</span>
            <span className="text-rose-400">-{diff.total_deleted}</span>
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {diff.files?.length || 0} file(s) touched
          </div>
        </div>
      </div>

      {/* Merge-Conflict Radar Badge */}
      <div
        className={`rounded-xl p-3 border text-xs flex items-center justify-between gap-2 ${
          merge.clean
            ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-200'
            : 'bg-red-950/40 border-red-600/60 text-red-100'
        }`}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 font-bold text-xs">
            <GitMerge className="w-4 h-4 shrink-0" />
            <span>Merge Status ({merge.base})</span>
          </div>
          {merge.clean ? (
            <div className="text-xs text-emerald-400 mt-1">
              ✓ Clean merge — no conflicts
            </div>
          ) : (
            <div className="text-xs text-red-300 font-mono mt-1 truncate">
              ⚠ Conflict in {merge.conflicts[0]?.path}{' '}
              {merge.conflicts[0]?.lines?.[0]
                ? `L${merge.conflicts[0].lines[0][0]}–${merge.conflicts[0].lines[0][1]}`
                : ''}
            </div>
          )}
        </div>
        {!merge.clean && (
          <button
            onClick={() => {
              setActiveInspectorTab('risk');
              runConflictResolver(merge.conflicts[0]?.path);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold shrink-0 shadow transition"
          >
            Resolve
          </button>
        )}
      </div>

      {/* Plain-English Risk Reasons */}
      <div className="pt-2 border-t border-slate-800 space-y-2">
        <div className="text-xs font-bold text-slate-200 flex items-center justify-between">
          <span>Why This Score?</span>
          {risk.coverage_estimated && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              est. coverage
            </span>
          )}
        </div>
        <ul className="space-y-2 text-xs text-slate-200 leading-relaxed">
          {(risk.reasons || []).slice(0, 3).map((reason, idx) => (
            <li
              key={idx}
              className="p-2.5 rounded-xl bg-slate-950/90 border border-slate-800 text-slate-200"
            >
              {reason}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
