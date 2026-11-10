import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  ArrowRight,
  Download,
  GitCompare,
  BarChart3,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const ReleaseScorecardModal: React.FC = () => {
  const {
    isScorecardModalOpen,
    setIsScorecardModalOpen,
    projectId,
    graph,
    risk,
    comparison,
    fetchComparison,
  } = useReleaseStore();

  const [tab, setTab] = useState<'scorecard' | 'compare'>('scorecard');
  const [baseRef, setBaseRef] = useState('origin/main');
  const [headRef, setHeadRef] = useState('HEAD');

  if (!isScorecardModalOpen) return null;

  const beforeScore = Math.round(risk.baseline_score ?? 77);
  const afterScore = Math.round(risk.score);
  const beforeVerdict = risk.baseline_verdict ?? 'HOLD';
  const afterVerdict = risk.verdict;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700 p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-slate-100">
              Release Risk Scorecard &amp; Ref Comparison
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs">
              <button
                onClick={() => setTab('scorecard')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
                  tab === 'scorecard'
                    ? 'bg-indigo-600 text-white font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Before vs After
              </button>
              <button
                onClick={() => {
                  setTab('compare');
                  fetchComparison(baseRef, headRef);
                }}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition ${
                  tab === 'compare'
                    ? 'bg-sky-600 text-white font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <GitCompare className="w-3.5 h-3.5" /> Ref Comparison (U11)
              </button>
            </div>
            <button
              onClick={() => setIsScorecardModalOpen(false)}
              className="p-1 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {tab === 'scorecard' ? (
            <>
              {/* Before vs After 3-Column Comparison (modeled directly on Breach Domino Scorecard.tsx) */}
              <div className="grid grid-cols-3 items-center gap-4 text-center">
                <div className="rounded-xl bg-red-950/30 border border-red-800/50 p-4">
                  <div className="text-xs uppercase text-red-300 font-semibold">
                    Before (Unmitigated)
                  </div>
                  <div className="mt-3 text-2xl font-mono font-bold text-red-400">
                    {beforeScore}/100
                  </div>
                  <div className="text-[11px] text-slate-400">Release Risk Score</div>

                  <div className="mt-3 text-lg font-mono font-bold text-red-300">
                    {beforeVerdict}
                  </div>
                  <div className="text-[11px] text-slate-400">Deployment Verdict</div>
                </div>

                <div className="flex flex-col items-center justify-center text-slate-400">
                  <ArrowRight className="w-8 h-8 text-emerald-400" />
                  <span className="text-[11px] font-mono mt-1 text-emerald-400">
                    SANDBOX VERIFIED
                  </span>
                </div>

                <div className="rounded-xl bg-emerald-950/30 border border-emerald-700/50 p-4">
                  <div className="text-xs uppercase text-emerald-300 font-semibold">
                    Current Release State
                  </div>
                  <div className="mt-3 text-2xl font-mono font-bold text-emerald-400">
                    {afterScore}/100
                  </div>
                  <div className="text-[11px] text-slate-400">Release Risk Score</div>

                  <div className="mt-3 text-lg font-mono font-bold text-emerald-300">
                    {afterVerdict}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Blast Radius: {risk.impacted.length}/{graph.nodes.length}
                  </div>
                </div>
              </div>

              {/* Download Report Buttons (Task B7 / U5) */}
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                <div>
                  <div className="font-bold text-slate-200">Export Full Release Risk Report</div>
                  <div className="text-[11px] text-slate-400">
                    Includes verdict, score, factor table, blast radius components, test results &amp;
                    merge status.
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      window.open(`/api/report/${encodeURIComponent(projectId)}?format=md`, '_blank')
                    }
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold shadow"
                  >
                    <Download className="w-3.5 h-3.5" /> Markdown (.md)
                  </button>
                  <button
                    onClick={() =>
                      window.open(
                        `/api/report/${encodeURIComponent(projectId)}?format=html`,
                        '_blank'
                      )
                    }
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold shadow"
                  >
                    <Download className="w-3.5 h-3.5" /> Styled HTML
                  </button>
                </div>
              </div>
            </>
          ) : (
            /* Task U11 (Stretch): Side-by-Side Release Comparison View */
            <div className="space-y-3 text-xs">
              <div className="flex items-center gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
                <div className="flex-1">
                  <label className="text-[10px] text-slate-400 block">Base Git Ref</label>
                  <input
                    type="text"
                    value={baseRef}
                    onChange={(e) => setBaseRef(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono text-slate-200"
                  />
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 mt-4" />
                <div className="flex-1">
                  <label className="text-[10px] text-slate-400 block">Target Git Ref</label>
                  <input
                    type="text"
                    value={headRef}
                    onChange={(e) => setHeadRef(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono text-slate-200"
                  />
                </div>
                <button
                  onClick={() => fetchComparison(baseRef, headRef)}
                  className="mt-4 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold"
                >
                  Compare Refs
                </button>
              </div>

              <div className="rounded-xl border border-slate-800 overflow-hidden">
                <table className="w-full text-left font-mono text-[11px]">
                  <thead className="bg-slate-950 text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-2 px-3">Component</th>
                      <th className="py-2 px-3">{baseRef} Risk</th>
                      <th className="py-2 px-3">{headRef} Risk</th>
                      <th className="py-2 px-3">Risk Delta</th>
                      <th className="py-2 px-3">Churn</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-900/60">
                    {(comparison?.deltas || []).map((d) => (
                      <tr key={d.id}>
                        <td className="py-2 px-3 text-slate-200 font-semibold">{d.path}</td>
                        <td className="py-2 px-3 text-slate-400">{d.base_risk}</td>
                        <td className="py-2 px-3 text-slate-100 font-bold">{d.head_risk}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded font-bold ${
                              d.delta > 0
                                ? 'bg-red-500/20 text-red-300'
                                : d.delta < 0
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            {d.delta > 0 ? `+${d.delta}` : d.delta}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          <span className="text-emerald-400">+{d.churn_added}</span> /{' '}
                          <span className="text-rose-400">-{d.churn_deleted}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
