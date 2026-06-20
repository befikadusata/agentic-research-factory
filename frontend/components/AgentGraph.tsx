"use client";

import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { RunStatus } from "@/lib/types";

type NodeState = "idle" | "running" | "complete" | "error";

import { RUN_STATUS_MAP, PIPELINE } from "@/lib/types";

const EDGES: Edge[] = PIPELINE.slice(0, -1).map((n, i) => ({
  id: `e${i}`,
  source: n.id,
  target: PIPELINE[i + 1].id,
  style: { stroke: "#52525b" },
}));

function nodeStateFromStatus(status: RunStatus, nodeId: string): NodeState {
  const order = PIPELINE.map(n => n.id);
  const idx = order.indexOf(nodeId);
  const activeIdx = RUN_STATUS_MAP[status] ?? 0;
  if (status === "failed") return idx <= activeIdx ? "error" : "idle";
  if (idx < activeIdx)  return "complete";
  if (idx === activeIdx) return "running";
  return "idle";
}

const STATE_STYLES: Record<NodeState, React.CSSProperties> = {
  idle:     { background: "#27272a", border: "1px solid #52525b", color: "#a1a1aa" },
  running:  { background: "#1e1b4b", border: "2px solid #7c3aed", color: "#c4b5fd", animation: "pulse 1.5s infinite" },
  complete: { background: "#14532d", border: "2px solid #16a34a", color: "#86efac" },
  error:    { background: "#450a0a", border: "2px solid #dc2626", color: "#fca5a5" },
};

interface Props {
  status: RunStatus;
  onNodeClick?: (nodeId: string) => void;
}

export function AgentGraph({ status, onNodeClick }: Props) {
  const initialNodes: Node[] = useMemo(
    () =>
      PIPELINE.map((n, i) => ({
        id: n.id,
        position: { x: i * 160, y: 60 },
        data: { label: n.label },
        style: { ...STATE_STYLES[nodeStateFromStatus(status, n.id)], borderRadius: 8, padding: "8px 14px", fontSize: 13, fontWeight: 500 },
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(EDGES);

  useEffect(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        style: {
          ...STATE_STYLES[nodeStateFromStatus(status, n.id)],
          borderRadius: 8,
          padding: "8px 14px",
          fontSize: 13,
          fontWeight: 500,
        },
      }))
    );
  }, [status, setNodes]);

  return (
    <div style={{ height: 180 }} className="rounded-xl border border-zinc-800 overflow-hidden">
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }`}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll={false}
        panOnDrag={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#27272a" gap={20} />
      </ReactFlow>
    </div>
  );
}
