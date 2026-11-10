import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  Server,
  Globe,
  Database,
  FileCode2,
  Layout,
  FlaskConical,
  Crown,
  ShieldCheck,
  ShieldAlert,
  Bug,
  GitCommitHorizontal,
  Flame,
} from 'lucide-react';
import { CNode, NodeKind } from '../../../shared/types';

export interface ReleaseNodeData extends Record<string, unknown> {
  node: CNode;
  isShockwaveActive: boolean;
  isSelected: boolean;
  isExecuting?: boolean;
}

const kindIcons: Record<NodeKind, React.ComponentType<{ className?: string }>> = {
  route: Globe,
  service: Server,
  module: FileCode2,
  view: Layout,
  infra: Database,
  sandbox: FlaskConical,
};

export const ReleaseNode: React.FC<NodeProps> = ({ data }) => {
  const { node, isShockwaveActive, isSelected, isExecuting } = data as unknown as ReleaseNodeData;
  const Icon = kindIcons[node.kind] || FileCode2;

  const isFailing = node.status === 'failing';
  const isChanged = node.status === 'changed';
  const isImpacted = node.status === 'impacted' || isShockwaveActive;
  const hasHighDefectGravity = node.defect_score >= 5.0;

  let borderColor = 'border-emerald-500/70';
  let bgGradient = 'from-slate-900/95 to-slate-950/95';
  let statusBadge = 'OK';
  let statusColor = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';

  if (isExecuting) {
    borderColor = 'border-blue-400 ring-2 ring-blue-500/80';
    bgGradient = 'from-blue-950/90 to-slate-950/95';
    statusBadge = '⚡ RUNNING';
    statusColor = 'bg-blue-500/35 text-blue-100 border-blue-400 animate-pulse';
  } else if (isFailing) {
    borderColor = 'border-red-500';
    bgGradient = 'from-slate-900/95 to-slate-950/95';
    statusBadge = 'FAILED';
    statusColor = 'bg-red-500/25 text-red-200 border-red-400/70';
  } else if (isChanged) {
    borderColor = 'border-amber-400';
    bgGradient = 'from-slate-900/95 to-slate-950/95';
    statusBadge = 'CHANGED';
    statusColor = 'bg-amber-500/25 text-amber-200 border-amber-400/60';
  } else if (isImpacted) {
    borderColor = 'border-rose-500';
    bgGradient = 'from-slate-900/95 to-slate-950/95';
    statusBadge = node.depth !== undefined ? `WAVE L${node.depth}` : 'IMPACTED';
    statusColor = 'bg-rose-500/25 text-rose-200 border-rose-400/70';
  } else if (node.kind === 'sandbox') {
    borderColor = 'border-cyan-400';
    bgGradient = 'from-cyan-950/85 to-slate-950/95';
    statusBadge = 'SANDBOX';
    statusColor = 'bg-cyan-500/25 text-cyan-200 border-cyan-400/60';
  }

  const crownRing = node.is_crown_jewel && !isExecuting
    ? 'ring-1 ring-amber-400/70'
    : '';
  const selectedRing = isSelected && !isExecuting
    ? 'ring-2 ring-sky-400 shadow-[0_0_20px_rgba(56,189,248,0.5)]'
    : '';

  const covPercent =
    node.coverage !== null && node.coverage !== undefined
      ? Math.round(node.coverage * 100)
      : null;

  const churnTotal = (node.churn?.added || 0) + (node.churn?.deleted || 0);

  return (
    <div
      style={{
        boxShadow: isExecuting
          ? '0 0 26px rgba(59, 130, 246, 0.9), 0 0 50px rgba(37, 99, 235, 0.55)'
          : '0 10px 25px rgba(0, 0, 0, 0.55)',
      }}
      className={`relative min-w-[235px] max-w-[265px] rounded-2xl border-2 ${borderColor} bg-gradient-to-b ${bgGradient} p-3.5 text-slate-100 backdrop-blur-md transition-all duration-300 ${crownRing} ${selectedRing} ${
        isExecuting ? 'node-executing-blue-glow' : 'shadow-xl'
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3.5 !h-3.5 !bg-sky-400 !border-2 !border-slate-950 hover:!scale-125 transition-transform"
        title="Target Handle — Drag wire here to connect"
      />

      {isExecuting ? (
        <div className="absolute -top-3 left-3 flex items-center gap-1 rounded-full bg-blue-500 px-2.5 py-0.5 text-[10px] font-extrabold text-white shadow-[0_0_12px_rgba(59,130,246,0.9)] animate-pulse">
          ⚡ EXECUTING NODE
        </div>
      ) : node.is_crown_jewel ? (
        <div className="absolute -top-3 left-3 flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow">
          <Crown className="w-3 h-3" /> CROWN JEWEL
        </div>
      ) : null}

      {node.kind === 'sandbox' ? (
        <div className="absolute -top-3 right-2.5 flex items-center gap-1 rounded-full bg-cyan-400 px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow">
          <FlaskConical className="w-3 h-3" /> SANDBOX
        </div>
      ) : hasHighDefectGravity ? (
        <div
          className="absolute -top-3 right-2.5 flex items-center gap-1 rounded-full bg-rose-500 px-2.5 py-0.5 text-[10px] font-extrabold text-white shadow"
          title={`Bug Gravity: ${node.defect_score}/10 from 180d git fixes & reverts`}
        >
          <Bug className="w-3 h-3" /> BUG {node.defect_score}/10
        </div>
      ) : null}

      {/* Header Row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className={`p-2 rounded-xl shrink-0 ${
              isExecuting
                ? 'bg-blue-500/30 text-blue-300'
                : isFailing
                ? 'bg-red-500/20 text-red-400'
                : isChanged
                ? 'bg-amber-500/20 text-amber-300'
                : isImpacted
                ? 'bg-rose-500/20 text-rose-300'
                : node.kind === 'infra'
                ? 'bg-indigo-500/20 text-indigo-300'
                : 'bg-slate-800 text-sky-400'
            }`}
          >
            <Icon className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-[10.5px] uppercase tracking-wider text-slate-400 font-semibold">
              {node.kind} • {node.lang}
            </div>
            <div className="text-sm font-bold truncate text-white" title={node.path}>
              {node.label}
            </div>
          </div>
        </div>

        <span
          className={`px-2 py-0.5 rounded-md border text-[10px] font-mono font-bold shrink-0 ${statusColor}`}
        >
          {statusBadge}
        </span>
      </div>

      {/* Metrics Footer Row */}
      <div className="mt-3 pt-2.5 border-t border-slate-800/90 flex items-center justify-between text-xs gap-1.5">
        <span
          className={`px-2 py-0.5 rounded-md font-mono font-bold ${
            node.risk >= 65
              ? 'bg-red-500/20 text-red-300 border border-red-500/30'
              : node.risk >= 35
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/25'
          }`}
        >
          Risk {Math.round(node.risk)}
        </span>

        {covPercent !== null ? (
          <span
            className={`flex items-center gap-1 px-2 py-0.5 rounded-md font-mono ${
              covPercent >= 70
                ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-700/40'
                : covPercent >= 40
                ? 'bg-amber-950/60 text-amber-300 border border-amber-700/40'
                : 'bg-red-950/60 text-red-300 border border-red-700/40'
            }`}
          >
            {covPercent >= 60 ? (
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            )}
            {covPercent}%{node.coverage_estimated ? ' est.' : ''}
          </span>
        ) : (
          <span className="text-[11px] font-mono text-slate-400">INFRA</span>
        )}

        {churnTotal > 0 ? (
          <span className="flex items-center gap-0.5 font-mono text-[11px] bg-slate-900 px-2 py-0.5 rounded-md border border-slate-700">
            <GitCommitHorizontal className="w-3 h-3 text-sky-400" />
            <span className="text-emerald-400">+{node.churn.added}</span>
            <span className="text-slate-500">/</span>
            <span className="text-rose-400">-{node.churn.deleted}</span>
          </span>
        ) : null}
      </div>

      {isImpacted && node.impact !== undefined && (
        <div className="mt-2 flex items-center justify-between px-2.5 py-1 rounded-lg bg-rose-950/60 border border-rose-700/50 text-[11px] font-mono text-rose-200">
          <span className="flex items-center gap-1 font-semibold">
            <Flame className="w-3 h-3 text-rose-400" /> Shockwave
          </span>
          <span>
            {Math.round(node.impact * 100)}% • Depth L{node.depth ?? 1}
          </span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3.5 !h-3.5 !bg-emerald-400 !border-2 !border-slate-950 hover:!scale-125 transition-transform"
        title="Source Handle — Drag wire to another node to synthesize connection"
      />
    </div>
  );
};
