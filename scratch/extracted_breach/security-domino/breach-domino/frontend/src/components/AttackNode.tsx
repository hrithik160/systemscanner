import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  Printer,
  Laptop,
  Server,
  KeyRound,
  Database,
  ShieldAlert,
  Crown,
  Crosshair,
  ShieldCheck,
} from 'lucide-react';
import { GNode } from '../../shared/types';

const iconMap = {
  IoT: Printer,
  Workstation: Laptop,
  Server: Server,
  IAM: KeyRound,
  Database: Database,
  Decoy: Crosshair,
};

export const AttackNode: React.FC<NodeProps> = ({ data }) => {
  const node = data as unknown as GNode & { isOnSimPath?: boolean };
  const Icon = iconMap[node.type] || Server;
  const isPatched = node.vulnerabilities.length === 0 && node.cvss_score <= 1.0 && !node.is_crown_jewel && !node.is_decoy;

  const statusStyles = {
    secure: isPatched
      ? 'bg-[#062c20]/95 border-emerald-500/80 text-emerald-100 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
      : 'bg-[#0e091d]/95 border-[#2d1b54] text-slate-100 shadow-[0_4px_15px_rgba(0,0,0,0.5)]',
    compromised:
      'bg-red-950/90 border-red-500 text-red-100 shadow-[0_0_24px_rgba(239,68,68,0.65)] animate-pulse',
    isolated: 'bg-[#06030c]/70 border-slate-800 text-slate-500 opacity-60',
  }[node.status];

  const crownRing = node.is_crown_jewel
    ? 'ring-2 ring-amber-400 shadow-[0_0_25px_rgba(251,191,36,0.5)]'
    : node.is_decoy
    ? 'ring-2 ring-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.5)]'
    : node.isOnSimPath
    ? 'ring-1 ring-red-400/80'
    : '';

  return (
    <div
      className={`relative min-w-[185px] rounded-2xl border-2 px-3.5 py-2.5 backdrop-blur-md transition-all ${statusStyles} ${crownRing}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-[#8b5cf6] !w-2.5 !h-2.5" />

      {node.is_crown_jewel && (
        <div className="absolute -top-3 -right-2 flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-0.5 text-[10px] font-bold text-slate-950 shadow-lg">
          <Crown className="w-3 h-3 text-slate-950" /> CROWN JEWEL
        </div>
      )}

      {node.is_decoy && (
        <div className="absolute -top-3 -right-2 flex items-center gap-1 rounded-full bg-emerald-400 px-2.5 py-0.5 text-[10px] font-bold text-slate-950 shadow-lg">
          <Crosshair className="w-3 h-3 text-slate-950" /> HONEYPOT
        </div>
      )}

      {isPatched && (
        <div className="absolute -top-3 -left-2 flex items-center gap-1 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold text-white shadow">
          <ShieldCheck className="w-3 h-3" /> SHIELDED
        </div>
      )}

      <div className="flex items-center gap-2.5">
        <div
          className={`p-2 rounded-xl ${
            node.status === 'compromised'
              ? 'bg-red-500/20 text-red-400'
              : node.is_decoy || isPatched
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'bg-[#1b1035] text-[#c084fc]'
          }`}
        >
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold truncate">{node.label}</div>
          <div className="text-[10px] text-slate-400 font-mono truncate">
            {node.refs?.ip || node.type}
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between text-[10px]">
        <span
          className={`px-1.5 py-0.5 rounded-md font-mono font-semibold ${
            node.cvss_score >= 8
              ? 'bg-red-500/20 text-red-300'
              : node.cvss_score >= 4
              ? 'bg-amber-500/20 text-amber-300'
              : 'bg-emerald-500/20 text-emerald-300'
          }`}
        >
          CVSS {node.cvss_score.toFixed(1)}
        </span>

        {isPatched ? (
          <span className="flex items-center gap-1 text-emerald-400 font-medium">
            <ShieldCheck className="w-3 h-3" /> Patched
          </span>
        ) : node.vulnerabilities.length > 0 ? (
          <span className="flex items-center gap-1 text-amber-300">
            <ShieldAlert className="w-3 h-3" /> {node.vulnerabilities.length} CVE
          </span>
        ) : null}
      </div>

      <Handle type="source" position={Position.Right} className="!bg-[#8b5cf6] !w-2.5 !h-2.5" />
    </div>
  );
};

export default AttackNode;
