"use client";

import { useEffect, useRef, useState } from "react";
import type { LogEntry } from "@/lib/types";

const AGENT_COLORS: Record<string, string> = {
  "Senior Research Analyst":   "text-blue-400",
  "Strategic Insights Analyst": "text-amber-400",
  "Senior Content Writer":     "text-green-400",
  "Editor & Fact-Checker":     "text-purple-400",
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
    <div className="bg-zinc-950 rounded-lg border border-zinc-800 p-4 h-96 flex flex-col font-mono text-sm">
      <div className="flex gap-2 mb-3">
        <button onClick={() => setFilter("all")} className={`text-xs px-2 py-1 rounded ${filter === 'all' ? 'bg-zinc-700 text-white' : 'text-zinc-500'}`}>All</button>
        <button onClick={() => setFilter("error")} className={`text-xs px-2 py-1 rounded ${filter === 'error' ? 'bg-zinc-700 text-white' : 'text-zinc-500'}`}>Errors</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {filteredLogs.length === 0 && (
          <p className="text-zinc-500 italic">No logs found...</p>
        )}
        {filteredLogs.map((log, i) => (
          <div key={i} className="mb-2">
            <span className="text-zinc-600 text-[10px] mr-2 select-none tabular-nums">
              {formatTs(log.ts)}
            </span>
            <span className={`font-bold ${AGENT_COLORS[log.agent] ?? "text-zinc-300"}`}>
              [{log.agent}]
            </span>{" "}
            <span className={`whitespace-pre-wrap break-words ${log.message.toLowerCase().includes('error') ? 'text-red-400' : 'text-zinc-300'}`}>
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
