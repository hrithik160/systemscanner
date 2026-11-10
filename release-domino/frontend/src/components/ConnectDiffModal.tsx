import React from 'react';
import { X, GitPullRequest, Check, Sparkles, ArrowRight } from 'lucide-react';
import { useReleaseStore } from '../store/releaseStore';

export const ConnectDiffModal: React.FC = () => {
  const { pendingConnectProposal, setPendingConnectProposal, applyEdgeConnection } =
    useReleaseStore();

  if (!pendingConnectProposal) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700/90 p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
              <GitPullRequest className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                AI Connection Wiring Proposal
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">
                  AST &amp; GIT VALIDATED
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Review the local LLM&apos;s proposed endpoint, imports, and unified diff before applying.
              </p>
            </div>
          </div>
          <button
            onClick={() => setPendingConnectProposal(null)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source -> Target Banner */}
        <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
          <span className="text-sky-300 font-bold">
            {pendingConnectProposal.source_node_id || 'Caller'}
          </span>
          <ArrowRight className="w-4 h-4 text-emerald-400" />
          <span className="text-emerald-300 font-bold">
            {pendingConnectProposal.target_node_id || 'Callee'}
          </span>
        </div>

        {/* Proposed Endpoint & Rationale */}
        <div className="space-y-2 text-xs">
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-[10px] uppercase text-slate-400 font-semibold mb-1">
              Synthesized Endpoint / Call Signature
            </div>
            <div className="font-mono text-sky-300 font-bold">
              {pendingConnectProposal.endpoint}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-[10px] uppercase text-slate-400 font-semibold mb-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-purple-400" /> Architectural Rationale
            </div>
            <div className="text-slate-200 leading-relaxed">
              {pendingConnectProposal.rationale}
            </div>
          </div>

          {/* Unified Diff Preview */}
          <div>
            <div className="text-[10.5px] font-mono text-slate-400 mb-1">
              Unified Diff Patch Preview ({pendingConnectProposal.proposal_id}):
            </div>
            <pre className="p-3 rounded-xl bg-[#060911] border border-slate-800 font-mono text-[11px] text-emerald-300 overflow-x-auto max-h-56 leading-relaxed">
              {pendingConnectProposal.patch}
            </pre>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800 text-xs">
          <button
            onClick={() => setPendingConnectProposal(null)}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold"
          >
            Reject Proposal
          </button>
          <button
            onClick={() => applyEdgeConnection(pendingConnectProposal.proposal_id)}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center gap-1.5 shadow-lg"
          >
            <Check className="w-4 h-4" /> Approve &amp; Apply Wiring
          </button>
        </div>
      </div>
    </div>
  );
};
