import React, { useMemo, useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  EdgeTypes,
  Connection,
  NodeChange,
} from '@xyflow/react';
import { useReleaseStore } from '../store/releaseStore';
import { ReleaseNode } from './ReleaseNode';
import { ReleaseEdge } from './ReleaseEdge';
import { CyberWorld3D } from './CyberWorld3D';

const nodeTypes: NodeTypes = {
  releaseNode: ReleaseNode,
};

const edgeTypes: EdgeTypes = {
  releaseEdge: ReleaseEdge,
};

const LAYER_Z: Record<string, number> = {
  route: 140,
  view: 110,
  sandbox: 60,
  service: 30,
  module: -60,
  infra: -160,
};

export const ReleaseCanvas: React.FC = () => {
  const {
    graph,
    risk,
    selectedNodeId,
    selectNode,
    selectEdge,
    shockwaveStep,
    collapseFolders,
    updateNodePosition,
    proposeEdgeConnection,
    executingNodeIds,
    activeFlowEdgeIds,
    isProgramRunning,
    viewMode,
    setViewMode,
    setIsNodeStudioOpen,
  } = useReleaseStore() as any;

  const [rotX, setRotX] = useState<number>(24);
  const [rotY, setRotY] = useState<number>(-18);
  const [zoom3d, setZoom3d] = useState<number>(0.92);
  const [dragStart, setDragStart] = useState<{ x: number; y: number; rx: number; ry: number } | null>(null);

  const execSet = useMemo(() => new Set<string>(executingNodeIds || []), [executingNodeIds]);
  const flowEdgeSet = useMemo(() => new Set<string>(activeFlowEdgeIds || []), [activeFlowEdgeIds]);

  const impactMap = useMemo(() => {
    const map = new Map<string, { impact: number; depth: number }>();
    for (const item of risk.impacted || []) {
      map.set(item.id, { impact: item.impact, depth: item.depth });
    }
    return map;
  }, [risk.impacted]);

  const rfNodes: Node[] = useMemo(() => {
    const sourceNodes = graph.nodes || [];

    return sourceNodes.map((n: any, idx: number) => {
      const imp = impactMap.get(n.id);
      const isShockwaveActive =
        imp !== undefined &&
        (shockwaveStep === null ? imp.depth > 0 : imp.depth <= shockwaveStep);

      const fallbackX = 120 + (idx % 4) * 300;
      const fallbackY = 90 + Math.floor(idx / 4) * 155;

      const isExecuting =
        execSet.has(n.id) ||
        (isProgramRunning &&
          execSet.size === 0 &&
          (n.kind === 'service' || n.status === 'changed' || n.id.includes('main') || n.id.includes('server')));

      return {
        id: n.id,
        type: 'releaseNode',
        position: n.pos || { x: fallbackX, y: fallbackY },
        data: {
          node: {
            ...n,
            depth: imp?.depth ?? n.depth,
            impact: imp?.impact ?? n.impact,
          },
          isShockwaveActive,
          isSelected: selectedNodeId === n.id,
          isExecuting,
        },
      };
    });
  }, [graph.nodes, impactMap, shockwaveStep, selectedNodeId, collapseFolders, execSet, isProgramRunning]);

  const rfEdges: Edge[] = useMemo(() => {
    return (graph.edges || []).map((e: any) => {
      const targetImp = impactMap.get(e.target);
      const sourceImp = impactMap.get(e.source);
      const isShockwaveEdge =
        targetImp !== undefined &&
        sourceImp !== undefined &&
        (shockwaveStep === null || sourceImp.depth <= shockwaveStep);

      const isFlowEdge =
        flowEdgeSet.has(e.id) ||
        execSet.has(e.source) ||
        execSet.has(e.target) ||
        (isProgramRunning && (e.type === 'call' || e.type === 'service'));

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'releaseEdge',
        data: {
          edge: e,
          isShockwaveEdge,
          shockwaveDepth: sourceImp?.depth,
          isFlowEdge,
        },
      };
    });
  }, [graph.edges, impactMap, shockwaveStep, flowEdgeSet, execSet, isProgramRunning]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id);
      setIsNodeStudioOpen(true);
    },
    [selectNode, setIsNodeStudioOpen]
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      selectEdge(edge.id);
    },
    [selectEdge]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target) {
        proposeEdgeConnection(connection.source, connection.target);
      }
    },
    [proposeEdgeConnection]
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      for (const change of changes) {
        if (change.type === 'position' && change.position && change.id) {
          updateNodePosition(change.id, change.position);
        }
      }
    },
    [updateNodePosition]
  );

  if (viewMode === '3d') {
    return <CyberWorld3D />;
  }

  return (
    <div className="w-full h-screen bg-[#060911]">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onConnect={onConnect}
        onNodesChange={onNodesChange}
        fitView
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={24} size={1.5} />
        <Controls className="!bg-slate-900 !border-slate-700 !text-slate-200" />
        <MiniMap
          nodeColor={(n) => {
            const cnode = (n.data as any)?.node;
            const isExec = (n.data as any)?.isExecuting;
            if (isExec) return '#3b82f6';
            if (!cnode) return '#10b981';
            if (cnode.status === 'failing') return '#ef4444';
            if (cnode.status === 'changed') return '#f59e0b';
            if (cnode.status === 'impacted') return '#f43f5e';
            if (cnode.kind === 'sandbox') return '#06b6d4';
            return '#10b981';
          }}
          maskColor="rgba(6, 9, 17, 0.75)"
          className="!bg-slate-900/90 !border !border-slate-700 !rounded-xl"
        />
      </ReactFlow>
    </div>
  );
};
