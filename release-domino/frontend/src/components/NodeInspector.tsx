import React, { useState, useEffect } from 'react';
import {
  X,
  FileCode2,
  ShieldAlert,
  Cpu,
  Sparkles,
  Crown,
  Play,
  Save,
  GitMerge,
  FileDiff,
  FlaskRound,
  Layers,
  Scissors,
  Wrench,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const NodeInspector: React.FC = () => {
  const {
    selectedNodeId,
    selectedEdgeId,
    selectNode,
    selectEdge,
    nodeDetail,
    isSummarizing,
    summarizeSelectedNode,
    saveNodeCode,
    toggleCrownJewel,
    severEdge,
    graph,
    risk,
    diff,
    merge,
    lastTestRun,
    architecture,
    activeInspectorTab,
    setActiveInspectorTab,
    isRunningTests,
    runTests,
    isGeneratingTests,
    generateTestsForNode,
    generatedTestCode,
    setGeneratedTestCode,
    agentPrompt,
    setAgentPrompt,
    isRunningAgent,
    runAgentLoop,
    agentResult,
    runAntiPatternScan,
    antiPatternResult,
    runConflictResolver,
    conflictResolutionResult,
    runAutoHeal,
    autoHealResult,
  } = useReleaseStore();

  const [codeDraft, setCodeDraft] = useState<string>('');
  const [isSavingCode, setIsSavingCode] = useState(false);

  useEffect(() => {
    if (nodeDetail?.code !== undefined) {
      setCodeDraft(nodeDetail.code);
    }
  }, [nodeDetail?.id, nodeDetail?.code]);

  const selectedEdge = selectedEdgeId ? graph.edges.find((e) => e.id === selectedEdgeId) : null;

  const handleSaveCode = async () => {
    if (!selectedNodeId) return;
    setIsSavingCode(true);
    await saveNodeCode(selectedNodeId, codeDraft);
    setIsSavingCode(false);
  };

  return (
    <div className="fixed top-20 right-5 z-30 w-[445px] max-h-[80vh] flex flex-col rounded-2xl bg-slate-900/95 border border-slate-700/90 p-5 backdrop-blur-md shadow-2xl overflow-hidden transition-all">
      {/* Clean 3-Tab Navigation (Task U4: 1. Node X-Ray | 2. Risk & Tests | 3. Architecture) */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3.5">
        <div className="flex items-center gap-1.5 rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs flex-1">
          <button
            onClick={() => setActiveInspectorTab('xray')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              activeInspectorTab === 'xray'
                ? 'bg-sky-600 text-white font-bold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileCode2 className="w-3.5 h-3.5" />
            Node X-Ray
          </button>

          <button
            onClick={() => setActiveInspectorTab('risk')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              activeInspectorTab === 'risk'
                ? 'bg-rose-600 text-white font-bold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            Risk &amp; Tests
          </button>

          <button
            onClick={() => setActiveInspectorTab('arch')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              activeInspectorTab === 'arch'
                ? 'bg-indigo-600 text-white font-bold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            Architecture
          </button>
        </div>

        {(selectedNodeId || selectedEdgeId) && (
          <button
            onClick={() => {
              selectNode(null);
              selectEdge(null);
            }}
            className="ml-2 p-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
            title="Close Selection"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* TAB 1: NODE X-RAY */}
      {activeInspectorTab === 'xray' && (
        <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4 text-xs">
          {selectedEdge ? (
            <div className="space-y-3 rounded-xl bg-slate-950 p-4 border border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase px-2.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-bold">
                  Dependency Edge ({selectedEdge.type})
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Weight: {selectedEdge.weight}
                </span>
              </div>
              <div className="font-mono text-xs space-y-1.5 pt-1">
                <div>
                  Caller (Source): <span className="text-sky-300 font-bold">{selectedEdge.source}</span>
                </div>
                <div>
                  Callee (Target): <span className="text-emerald-300 font-bold">{selectedEdge.target}</span>
                </div>
              </div>
              <button
                onClick={() => severEdge(selectedEdge.id)}
                className="w-full py-2 rounded-xl bg-red-600/30 border border-red-500/50 hover:bg-red-600/40 text-red-200 font-bold flex items-center justify-center gap-1.5 transition"
              >
                <Scissors className="w-4 h-4" /> Sever Dependency Link
              </button>
            </div>
          ) : !nodeDetail ? (
            <div className="py-12 text-center text-slate-400 space-y-2.5">
              <FileCode2 className="w-10 h-10 mx-auto text-slate-600" />
              <p className="text-sm font-bold text-slate-200">Select Any Component on the Graph</p>
              <p className="text-xs text-slate-400 max-w-xs mx-auto leading-relaxed">
                Click any node on the canvas to inspect its source code, 3-bullet AI summary, defect
                history, and downstream blast radius.
              </p>
            </div>
          ) : (
            <>
              {/* Node Header */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded-md bg-sky-500/20 text-sky-300 font-semibold">
                      {nodeDetail.kind} • {nodeDetail.lang}
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-800 text-slate-200">
                      {nodeDetail.loc} LOC
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      Bug Gravity {nodeDetail.defect_score}/10
                    </span>
                  </div>
                  <h3 className="mt-2 text-base font-bold text-white font-mono break-all">
                    {nodeDetail.path}
                  </h3>
                </div>

                <button
                  onClick={() => toggleCrownJewel(nodeDetail.id)}
                  className={`px-3 py-1.5 rounded-xl border text-xs font-bold flex items-center gap-1.5 shrink-0 transition ${
                    nodeDetail.is_crown_jewel
                      ? 'border-amber-400/80 bg-amber-500/25 text-amber-200 shadow'
                      : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <Crown className="w-4 h-4 text-amber-400" />
                  {nodeDetail.is_crown_jewel ? 'Crown Jewel' : 'Set Crown'}
                </button>
              </div>

              {/* 3-Bullet Local LLM Summary Card */}
              <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 font-bold text-sky-300 text-xs">
                    <Sparkles className="w-4 h-4 text-sky-400" /> AI Component Summary
                  </span>
                  <button
                    onClick={() => summarizeSelectedNode(nodeDetail.id)}
                    disabled={isSummarizing}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-200"
                  >
                    <RefreshCw className={`w-3 h-3 ${isSummarizing ? 'animate-spin' : ''}`} />
                    {isSummarizing ? 'Summarizing...' : 'Refresh'}
                  </button>
                </div>

                {nodeDetail.cached_summary ? (
                  <>
                    <p className="text-xs text-slate-100 font-semibold leading-relaxed">
                      {nodeDetail.cached_summary.purpose}
                    </p>
                    <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside leading-relaxed">
                      {nodeDetail.cached_summary.summary.map((bullet, i) => (
                        <li key={i}>{bullet}</li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-xs text-slate-400">
                    Click Refresh to generate a 3-bullet plain-English summary.
                  </p>
                )}

                {nodeDetail.exports?.length > 0 && (
                  <div className="pt-2 border-t border-slate-800 flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] text-slate-400 font-semibold">Exports:</span>
                    {nodeDetail.exports.map((ex) => (
                      <span
                        key={ex}
                        className="px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-emerald-300 font-mono text-[11px]"
                      >
                        {ex}()
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Source Code Editor */}
              <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                    <FileCode2 className="w-4 h-4 text-emerald-400" /> Source Code ({nodeDetail.label})
                  </span>
                  <button
                    type="button"
                    onClick={handleSaveCode}
                    disabled={isSavingCode}
                    className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow transition disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {isSavingCode ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>

                <textarea
                  rows={8}
                  value={codeDraft}
                  onChange={(e) => setCodeDraft(e.target.value)}
                  spellCheck={false}
                  className="w-full rounded-xl bg-[#060911] border border-slate-800 p-3 text-xs font-mono text-slate-100 focus:border-sky-500 outline-none resize-y leading-relaxed"
                />
              </div>

              {/* Ask AI Agent to Modify */}
              <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
                <div className="font-bold text-purple-300 text-xs flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-purple-400" /> Ask AI Agent to Modify Code
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={agentPrompt}
                    onChange={(e) => setAgentPrompt(e.target.value)}
                    placeholder="e.g., Add a Redis rate limiter to login_route..."
                    className="flex-1 rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-slate-100 focus:border-purple-500 outline-none"
                  />
                  <button
                    onClick={() => runAgentLoop()}
                    disabled={isRunningAgent}
                    className="px-3.5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-1.5 shrink-0 shadow disabled:opacity-50"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    {isRunningAgent ? 'Running...' : 'Ask AI'}
                  </button>
                </div>

                {agentResult && (
                  <div className="mt-2 p-3 rounded-xl bg-purple-950/30 border border-purple-700/50 space-y-2 font-mono text-xs">
                    <div className="text-purple-200 font-sans font-semibold">
                      {agentResult.summary || 'Agent completed patch proposal:'}
                    </div>
                    {agentResult.patch && (
                      <pre className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-emerald-300 overflow-x-auto max-h-36">
                        {agentResult.patch}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 2: RELEASE RISK & TESTS */}
      {activeInspectorTab === 'risk' && (
        <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4 text-xs">
          {/* Factor-by-Factor Risk Breakdown */}
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="font-bold text-slate-100 text-xs flex items-center justify-between">
              <span>Risk Score Factor Breakdown</span>
              <span className="font-mono text-sky-400">{Math.round(risk.score)} / 100</span>
            </div>
            <div className="space-y-2.5">
              {(risk.factors || []).map((f, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-200">{f.name}</span>
                    <span className="font-mono text-sky-300 font-bold">
                      +{f.contribution.toFixed(1)} pts
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-sky-500"
                      style={{ width: `${Math.min(100, Math.round((f.value || 0) * 100))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Git Diff Counter */}
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-100 text-xs flex items-center gap-1.5">
                <FileDiff className="w-4 h-4 text-sky-400" /> Modified Files &amp; Line Hunks
              </span>
              <span className="font-mono text-xs">
                <span className="text-emerald-400 font-bold">+{diff.total_added}</span> /{' '}
                <span className="text-rose-400 font-bold">-{diff.total_deleted}</span>
              </span>
            </div>
            <div className="space-y-1.5 max-h-32 overflow-y-auto font-mono text-xs">
              {(diff.files || []).map((f, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800"
                >
                  <span className="text-slate-200 truncate">{f.path}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {f.hunks?.length > 0 && (
                      <span className="text-slate-400">
                        L{f.hunks[0].start}–{f.hunks[0].end}
                      </span>
                    )}
                    <span className="text-emerald-400">+{f.added}</span>
                    <span className="text-rose-400">-{f.deleted}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Merge-Conflict Radar */}
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-100 text-xs flex items-center gap-1.5">
                <GitMerge className="w-4 h-4 text-amber-400" /> Merge Radar vs {merge.base}
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-md text-xs font-mono font-bold ${
                  merge.clean
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-red-500/25 text-red-300'
                }`}
              >
                {merge.clean ? 'CLEAN' : `${merge.conflicts.length} CONFLICT`}
              </span>
            </div>

            {!merge.clean && (
              <div className="space-y-2">
                {merge.conflicts.map((c, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-red-950/40 border border-red-700/50 font-mono text-xs text-red-200"
                  >
                    <span>
                      {c.path}{' '}
                      {c.lines?.length ? `(L${c.lines[0][0]}–${c.lines[0][1]})` : ''}
                    </span>
                    <button
                      onClick={() => runConflictResolver(c.path)}
                      className="px-2.5 py-1 rounded-md bg-red-600 hover:bg-red-500 text-white text-xs font-sans font-bold"
                    >
                      AI Resolve
                    </button>
                  </div>
                ))}
              </div>
            )}

            {conflictResolutionResult && (
              <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-700/50 space-y-1.5 font-mono text-xs">
                <div className="text-emerald-300 font-sans font-bold">
                  ✓ AI Conflict Resolution ({conflictResolutionResult.strategy}):
                </div>
                <pre className="p-2 rounded bg-slate-950 text-emerald-200 overflow-x-auto max-h-28">
                  {conflictResolutionResult.resolved_code}
                </pre>
              </div>
            )}
          </div>

          {/* Sandbox Test & Coverage Runner */}
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-100 text-xs flex items-center gap-1.5">
                <FlaskRound className="w-4 h-4 text-emerald-400" /> Test &amp; Coverage Runner
              </span>
              {lastTestRun && (
                <div className="flex items-center gap-1.5 font-mono text-xs">
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                    PASS: {lastTestRun.passed}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-bold">
                    FAIL: {lastTestRun.failed}
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => runTests(false)}
                disabled={isRunningTests}
                className="py-2 px-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1 shadow disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" /> Run All
              </button>
              <button
                onClick={() => runTests(true)}
                disabled={isRunningTests}
                className="py-2 px-2.5 rounded-xl bg-sky-600/30 border border-sky-500/50 hover:bg-sky-600/50 text-sky-100 font-semibold text-xs flex items-center justify-center gap-1"
              >
                <Layers className="w-3.5 h-3.5" /> Impacted
              </button>
              <button
                onClick={() => generateTestsForNode(selectedNodeId || 'app/auth.py')}
                disabled={isGeneratingTests}
                className="py-2 px-2.5 rounded-xl bg-purple-600/30 border border-purple-500/50 hover:bg-purple-600/50 text-purple-100 font-semibold text-xs flex items-center justify-center gap-1"
              >
                <Sparkles className="w-3.5 h-3.5" />{' '}
                {isGeneratingTests ? 'Writing...' : 'AI Tests'}
              </button>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Test Suite Editor</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={runAutoHeal}
                    className="text-amber-300 hover:underline flex items-center gap-1 text-xs"
                  >
                    <Wrench className="w-3 h-3" /> Auto-Heal
                  </button>
                  {generatedTestCode && (
                    <button
                      onClick={() => runTests(false, generatedTestCode)}
                      className="px-2.5 py-0.5 rounded bg-emerald-600/30 border border-emerald-500/50 text-emerald-200 text-xs font-semibold"
                    >
                      Run Custom
                    </button>
                  )}
                </div>
              </div>
              <textarea
                rows={5}
                value={generatedTestCode}
                onChange={(e) => setGeneratedTestCode(e.target.value)}
                placeholder="Click 'AI Tests' to generate runnable pytest/jest unit tests for the selected node..."
                className="w-full rounded-xl bg-[#060911] border border-slate-800 p-2.5 text-xs font-mono text-emerald-200 focus:border-emerald-500 outline-none"
              />
            </div>

            {autoHealResult && (
              <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-700/50 text-xs text-amber-200">
                <span className="font-bold">Auto-Heal:</span> {autoHealResult.diagnosis}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: ARCHITECTURE & TECH STACK */}
      {activeInspectorTab === 'arch' && (
        <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4 text-xs">
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2">
            <div className="font-bold text-indigo-300 text-xs flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-indigo-400" /> Architecture Overview
            </div>
            <p className="text-xs text-slate-200 leading-relaxed">{architecture.summary}</p>
          </div>

          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="font-bold text-slate-100 text-xs">Detected Tech Stack</div>
            <div className="flex flex-wrap gap-2">
              {(architecture.stack || []).map((item) => (
                <span
                  key={item}
                  className="px-3 py-1 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-300 font-mono text-xs font-semibold"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="font-bold text-slate-100 text-xs">
              Infrastructure Links ({architecture.node_infra_links?.length || 0})
            </div>
            <div className="space-y-1.5 font-mono text-xs">
              {(architecture.node_infra_links || []).map((link, idx) => (
                <div
                  key={idx}
                  onClick={() => selectNode(link.node_id)}
                  className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 cursor-pointer hover:border-sky-500/50 transition"
                >
                  <span className="text-slate-200 truncate">{link.node_id}</span>
                  <span className="px-2.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold">
                    → {link.infra}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Anti-Pattern Scanner */}
          <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-300 text-xs flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-400" /> Anti-Pattern Check
              </span>
              <button
                onClick={() => runAntiPatternScan(selectedNodeId || 'app/auth.py')}
                className="px-3 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-bold"
              >
                Scan {selectedNodeId ? selectedNodeId.split('/').pop() : 'Module'}
              </button>
            </div>

            {antiPatternResult && (
              <div className="space-y-2 pt-1">
                {(antiPatternResult.flags || []).length === 0 ? (
                  <div className="text-emerald-400 flex items-center gap-1.5 text-xs">
                    <CheckCircle2 className="w-4 h-4" /> No anti-patterns detected.
                  </div>
                ) : (
                  (antiPatternResult.flags || []).map((fl: any, i: number) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-700/50 space-y-1"
                    >
                      <div className="flex items-center justify-between font-mono text-xs text-amber-300 font-bold">
                        <span>{fl.kind}</span>
                        <span>{fl.severity?.toUpperCase()}</span>
                      </div>
                      <p className="text-xs text-slate-200">{fl.message}</p>
                      <p className="text-xs text-emerald-300">Fix: {fl.suggestion}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
