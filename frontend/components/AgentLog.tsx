"use client";

import { useEffect, useRef, useState } from "react";
import type { LogEntry } from "@/lib/types";

// Agent identity hues — fixed per role, independent of state. See
// docs/design/factotum-design.md §2.6.
const AGENT_COLORS: Record<string, string> = {
  "Senior Research Analyst":    "var(--base-agent-researcher)",
  "Strategic Insights Analyst": "var(--base-agent-analyst)",
  "Senior Content Writer":      "var(--base-agent-writer)",
  "Editor & Fact-Checker":      "var(--base-agent-editor)",
};

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export function AgentLog({ logs }: { logs: LogEntry[] }) {
  const [filter, setFilter] = useState<"all" | "error">("all");
  const bottomRef = useRef<HTMLDivElement>(null);

  const filteredLogs = filter === "all"
    ? logs
    : logs.filter(l => l.message.toLowerCase().includes("error") || l.agent.toLowerCase().includes("error"));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="ftm-scanline relative bg-surface-1 rounded-lg border border-border-subtle p-4 h-96 flex flex-col font-mono text-sm">
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
          className={`text-xs px-2 py-1 rounded-sm transition-colors ${filter === "all" ? "bg-surface-3 text-content" : "text-content-muted hover:text-content-secondary"}`}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => setFilter("error")}
          aria-pressed={filter === "error"}
          className={`text-xs px-2 py-1 rounded-sm transition-colors ${filter === "error" ? "bg-surface-3 text-content" : "text-content-muted hover:text-content-secondary"}`}
        >
          Errors
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {filteredLogs.length === 0 && (
          <p className="text-content-muted italic">No logs found...</p>
        )}
        {filteredLogs.map((log, i) => (
          <div key={i} className="ftm-log-line mb-2 animate-log-in">
            <span className="text-content-muted text-[10px] mr-2 select-none tabular-nums">
              {formatTs(log.ts)}
            </span>
            <span className="font-bold" style={{ color: AGENT_COLORS[log.agent] ?? "var(--text-secondary)" }}>
              [{log.agent}]
            </span>{" "}
            <span className={`whitespace-pre-wrap break-words ${log.message.toLowerCase().includes("error") ? "text-content" : "text-content-secondary"}`}>
              {log.message.slice(0, 400)}
              {log.message.length > 400 && "…"}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
