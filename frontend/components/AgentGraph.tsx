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
import { PIPELINE, pipelineNodeState, type AgentState } from "@/lib/types";

const EDGES: Edge[] = PIPELINE.slice(0, -1).map((n, i) => ({
  id: `e${i}`,
  source: n.id,
  target: PIPELINE[i + 1].id,
  style: { stroke: "var(--node-edge-idle)" },
}));

const STATE_STYLES: Record<AgentState, React.CSSProperties> = {
  idle:     { background: "var(--color-surface-2)", border: "1px solid var(--node-idle-border)", color: "var(--text-muted)" },
  active:   { background: "var(--node-active-fill)", border: "1px solid var(--node-active-border)", color: "var(--text-primary)", boxShadow: "var(--node-active-glow)" },
  thinking: { background: "rgb(var(--rgb-violet) / 0.10)", border: "1px solid var(--color-agent-thinking)", color: "var(--text-primary)" },
  complete: { background: "rgb(var(--rgb-mint) / 0.12)", border: "1px solid var(--node-complete-border)", color: "var(--color-agent-complete)" },
  error:    { background: "rgb(var(--rgb-rose) / 0.12)", border: "1px solid var(--node-error-border)", color: "var(--color-agent-error)" },
  paused:   { background: "rgb(var(--rgb-amber) / 0.12)", border: "1px solid var(--node-paused-border)", color: "var(--color-agent-paused)" },
};

const STATE_ANIMATION: Partial<Record<AgentState, string>> = {
  active: "animate-node-pulse",
  paused: "animate-hitl-breath",
  error: "animate-node-shake",
};

const STATE_GLYPH: Partial<Record<AgentState, string>> = {
  complete: "✓ ",
  error: "✕ ",
  paused: "▮▮ ",
};

interface Props {
  status: RunStatus;
  failedAtStatus?: RunStatus | null;
  onNodeClick?: (nodeId: string) => void;
}

function nodeFor(n: (typeof PIPELINE)[number], i: number, status: RunStatus, failedAtStatus?: RunStatus | null): Node {
  const state = pipelineNodeState(status, n.id, failedAtStatus);
  return {
    id: n.id,
    position: { x: i * 160, y: 60 },
    data: { label: `${STATE_GLYPH[state] ?? ""}${n.label}` },
    className: `ftm-node ${STATE_ANIMATION[state] ?? ""}`,
    style: { ...STATE_STYLES[state], borderRadius: 8, padding: "8px 14px", fontSize: 13, fontWeight: 500 },
  };
}

export function AgentGraph({ status, failedAtStatus, onNodeClick }: Props) {
  const initialNodes: Node[] = useMemo(
    () => PIPELINE.map((n, i) => nodeFor(n, i, status, failedAtStatus)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(EDGES);

  useEffect(() => {
    setNodes(PIPELINE.map((n, i) => nodeFor(n, i, status, failedAtStatus)));
  }, [status, failedAtStatus, setNodes]);

  return (
    <div style={{ height: 180 }} className="rounded-xl border border-border-subtle overflow-hidden bg-surface-2">
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
        <Background color="var(--color-border-subtle)" gap={20} />
      </ReactFlow>
    </div>
  );
}
