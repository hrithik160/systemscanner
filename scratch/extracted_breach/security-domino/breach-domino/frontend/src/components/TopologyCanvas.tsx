import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Node,
  Edge,
  NodeMouseHandler,
  EdgeMouseHandler,
} from '@xyflow/react';
import { useGraphStore } from '../store/graphStore';
import { AttackNode } from './AttackNode';
import { AttackEdge } from './AttackEdge';

const nodeTypes = { attackNode: AttackNode };
const edgeTypes = { attackEdge: AttackEdge };

export const TopologyCanvas: React.FC = () => {
  const {
    mode,
    liveGraph,
    whatIfGraph,
    simPlayback,
    activeTool,
    selectNode,
    selectEdge,
    patchNode,
    firewallEdge,
  } = useGraphStore();

  const graph = mode === 'live' ? liveGraph : whatIfGraph;

  // Progressive revealed path sets from unified simPlayback engine
  const activePathNodes = useMemo(() => {
    return new Set(simPlayback.revealedNodes);
  }, [simPlayback.revealedNodes]);

  const activePathEdges = useMemo(() => {
    const set = new Set(simPlayback.revealedEdges);
    if (simPlayback.activeEdgeId) set.add(simPlayback.activeEdgeId);
    return set;
  }, [simPlayback.revealedEdges, simPlayback.activeEdgeId]);

  const rfNodes: Node[] = useMemo(
    () =>
      graph.nodes.map((n, idx) => ({
        id: n.id,
        type: 'attackNode',
        position: n.pos || { x: 120 + (idx % 5) * 210, y: 100 + Math.floor(idx / 5) * 150 },
        data: {
          ...n,
          isOnSimPath: activePathNodes.has(n.id),
          isCurrentTarget: n.id === simPlayback.targetNodeId,
        },
      })),
    [graph.nodes, activePathNodes, simPlayback.targetNodeId]
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'attackEdge',
        data: {
          ...e,
          isOnSimPath: activePathEdges.has(e.id),
          isCurrentlyTraversing: e.id === simPlayback.activeEdgeId,
        },
      })),
    [graph.edges, activePathEdges, simPlayback.activeEdgeId]
  );

  const onNodeClick: NodeMouseHandler = (_, node) => {
    if (activeTool === 'patch') {
      patchNode(node.id);
    } else {
      selectNode(node.id);
    }
  };

  const onEdgeClick: EdgeMouseHandler = (_, edge) => {
    if (activeTool === 'scissors') {
      firewallEdge(edge.id);
    } else {
      selectEdge(edge.id);
    }
  };

  const cursorClass =
    mode === 'whatif' && activeTool === 'scissors'
      ? 'cursor-crosshair'
      : mode === 'whatif' && activeTool === 'patch'
      ? 'cursor-pointer'
      : '';

  return (
    <div className={`w-full h-full bg-[#06030c] ${cursorClass}`}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={() => {
          selectNode(null);
          selectEdge(null);
        }}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e1035" gap={24} size={1} />
        <Controls className="!bg-[#0e091d] !border-[#2d1b54] !fill-[#c4b5fd]" />
      </ReactFlow>
    </div>
  );
};

export default TopologyCanvas;
