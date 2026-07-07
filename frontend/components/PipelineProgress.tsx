import { PIPELINE, RUN_STATUS_MAP, pipelineNodeState, type AgentState, type RunStatus } from "@/lib/types";

const STATE_BAR_CLASS: Record<AgentState, string> = {
  idle: "bg-surface-3",
  active: "bg-agent-active animate-node-pulse",
  thinking: "bg-agent-thinking",
  complete: "bg-agent-complete",
  error: "bg-agent-error",
  paused: "bg-agent-paused animate-hitl-breath",
};

/** Compact, per-run pipeline progress — one segment per stage. See docs/design/factotum-implementation.md §7.2. */
export function PipelineProgress({ status }: { status: RunStatus }) {
  const activeIdx = Math.max(RUN_STATUS_MAP[status] ?? 0, 0);

  return (
    <div
      className="flex gap-1"
      role="progressbar"
      aria-label="Pipeline progress"
      aria-valuenow={activeIdx}
      aria-valuemin={0}
      aria-valuemax={PIPELINE.length - 1}
    >
      {PIPELINE.map((n) => {
        const state = pipelineNodeState(status, n.id);
        return (
          <span
            key={n.id}
            data-state={state}
            className={`h-1.5 flex-1 rounded-pill transition-colors duration-base ${STATE_BAR_CLASS[state]}`}
          />
        );
      })}
    </div>
  );
}
