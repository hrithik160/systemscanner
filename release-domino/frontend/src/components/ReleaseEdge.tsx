import React from 'react';
import { BaseEdge, EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react';
import { CEdge } from '../../../shared/types';

export interface ReleaseEdgeData extends Record<string, unknown> {
  edge: CEdge;
  isShockwaveEdge: boolean;
  shockwaveDepth?: number;
  isFlowEdge?: boolean;
}

export const ReleaseEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const { edge, isShockwaveEdge, shockwaveDepth, isFlowEdge } = (data || {}) as ReleaseEdgeData;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  let strokeColor = '#475569';
  let strokeWidth = 1.8;
  let strokeDasharray: string | undefined = undefined;

  if (isShockwaveEdge) {
    strokeColor = '#f43f5e'; // Crimson shockwave
    strokeWidth = 3.2;
  } else if (isFlowEdge) {
    strokeColor = '#38bdf8'; // Electric blue / cyan project flow
    strokeWidth = 2.8;
  } else if (edge?.type === 'infra') {
    strokeColor = '#6366f1';
    strokeDasharray = '5 4';
  } else if (edge?.type === 'call') {
    strokeColor = '#38bdf8';
    strokeWidth = 2.1;
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: strokeColor,
          strokeWidth,
          strokeDasharray,
          filter: isShockwaveEdge
            ? 'drop-shadow(0 0 8px rgba(244,63,94,0.85))'
            : isFlowEdge
            ? 'drop-shadow(0 0 10px rgba(56,189,248,0.9))'
            : undefined,
          transition: 'stroke 0.25s ease, stroke-width 0.25s ease',
        }}
      />

      {/* Task U6: Animated Crimson Shockwave Domino Pulses along active impact edges */}
      {isShockwaveEdge && (
        <svg>
          <circle r="5" fill="#fb7185" filter="drop-shadow(0 0 6px #f43f5e)">
            <animateMotion
              dur="1.05s"
              repeatCount="indefinite"
              path={edgePath}
              keyPoints="1;0"
              keyTimes="0;1"
              calcMode="linear"
            />
          </circle>
        </svg>
      )}

      {/* Animated Electric Blue Project Flow Pulses along active conduits */}
      {isFlowEdge && !isShockwaveEdge && (
        <svg>
          <circle r="5" fill="#38bdf8" filter="drop-shadow(0 0 8px #0284c7)">
            <animateMotion
              dur="0.85s"
              repeatCount="indefinite"
              path={edgePath}
              calcMode="linear"
            />
          </circle>
          <circle r="2.5" fill="#ffffff">
            <animateMotion
              dur="0.85s"
              repeatCount="indefinite"
              path={edgePath}
              calcMode="linear"
            />
          </circle>
        </svg>
      )}

      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className={`px-1.5 py-0.5 rounded text-[9.5px] font-mono border backdrop-blur-sm transition ${
            isShockwaveEdge
              ? 'bg-rose-950/90 border-rose-500/80 text-rose-200 font-bold shadow-[0_0_10px_rgba(244,63,94,0.5)]'
              : isFlowEdge
              ? 'bg-blue-950/90 border-blue-400 text-blue-200 font-bold shadow-[0_0_10px_rgba(59,130,246,0.6)]'
              : 'bg-slate-900/85 border-slate-700/80 text-slate-400'
          }`}
        >
          {edge?.type || 'import'}
          {isShockwaveEdge && shockwaveDepth !== undefined ? ` • L${shockwaveDepth}` : ''}
          {isFlowEdge && !isShockwaveEdge ? ' • FLOW' : ''}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};
