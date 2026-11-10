import React from 'react';
import { BaseEdge, EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react';
import { GEdge } from '../../shared/types';
import { Ban } from 'lucide-react';

export const AttackEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const edge = data as unknown as GEdge & { isOnSimPath?: boolean };
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isFirewalled = edge.status === 'firewalled';
  const isActive = edge.status === 'active_attack';
  const isSimPath = edge.isOnSimPath && !isFirewalled;

  const strokeColor = isFirewalled
    ? '#ef4444'
    : isActive || isSimPath
    ? '#f43f5e'
    : '#8b5cf6';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: strokeColor,
          strokeWidth: isActive || isSimPath ? 2.5 : 1.4,
          strokeDasharray: isFirewalled ? '5 5' : isActive || isSimPath ? '6 4' : undefined,
          opacity: isFirewalled ? 0.45 : isSimPath ? 0.95 : 0.6,
        }}
      />

      {/* Traveling photon particle along active attack path */}
      {(isActive || isSimPath) && (
        <g>
          {[0, 0.6, 1.2].map((delay, idx) => (
            <circle
              key={idx}
              r={isActive ? 4 : 3.5}
              fill="#ffffff"
              className="drop-shadow-[0_0_8px_rgba(239,68,68,1)]"
            >
              <animateMotion
                dur="1.6s"
                begin={`${delay}s`}
                repeatCount="indefinite"
                path={edgePath}
              />
            </circle>
          ))}
        </g>
      )}

      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className={`px-2 py-0.5 rounded-md text-[9px] font-mono border backdrop-blur-md ${
            isFirewalled
              ? 'bg-red-950/90 border-red-500 text-red-300 font-bold flex items-center gap-1 shadow-lg'
              : isActive || isSimPath
              ? 'bg-[#1b0a1f]/95 border-red-500 text-red-200 font-bold shadow-[0_0_10px_rgba(239,68,68,0.5)]'
              : 'bg-[#0e091d]/90 border-[#2d1b54] text-[#c4b5fd]'
          }`}
        >
          {isFirewalled ? (
            <>
              <Ban className="w-2.5 h-2.5 text-red-400" />
              <span className="line-through">CUT // FIREWALLED</span>
            </>
          ) : (
            `${edge.protocol} • ${edge.exploit_time_sec}s`
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default AttackEdge;
