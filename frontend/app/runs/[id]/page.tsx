"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getRun } from "@/lib/api";
import { AgentLog } from "@/components/AgentLog";
import { HitlModal } from "@/components/HitlModal";
import { OutputPanel } from "@/components/OutputPanel";
import type { RunDetail, LogEntry } from "@/lib/types";
import { VERTICALS } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  pending:                    "Pending",
  researching:                "Researching…",
  awaiting_hitl:              "Awaiting Review",
  awaiting_research_approval: "Awaiting Research Review",
  analyzing:                  "Analyzing…",
  awaiting_analysis_approval: "Awaiting Analysis Review",
  writing:                    "Writing…",
  awaiting_final_approval:    "Awaiting Final Review",
  complete:                   "Complete",
  failed:                     "Failed",
};

const HITL_STATUSES = new Set([
  "awaiting_research_approval",
  "awaiting_analysis_approval",
  "awaiting_final_approval",
]);

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [hitlSummary, setHitlSummary] = useState<string | null>(null);
  const [hitlStage, setHitlStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  
  useEffect(() => {
    getRun(id)
      .then((r) => {
        setRun(r);
        setLogs(r.logs ?? []);
        setStatus((prev) => (prev === "loading" ? r.status : prev));
        if (HITL_STATUSES.has(r.status)) {
          setHitlStage(r.status);
          const summary =
            r.status === "awaiting_research_approval" ? r.research_output :
            r.status === "awaiting_analysis_approval" ? r.analysis_output :
            r.final_output;
          if (summary) setHitlSummary(summary.slice(0, 2000));
        }
      })
      .catch((e) => setLoadError(e.message));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`${process.env.NEXT_PUBLIC_BACKEND_URL}/runs/${id}/stream`, { withCredentials: true });

    es.onmessage = (e) => {
        const parsed = JSON.parse(e.data);
        if (parsed.type === "log") {
            setLogs((prev) => [...prev, parsed.data]);
        } else if (parsed.type === "status") {
            setStatus(parsed.data.status);
        } else if (parsed.type === "hitl_required") {
            setHitlStage(parsed.data.stage);
            setHitlSummary(parsed.data.summary);
            setStatus(parsed.data.stage);
        } else if (parsed.type === "complete") {
            setStatus("complete");
            getRun(id).then(setRun);
        } else if (parsed.type === "error") {
            setStatus("failed");
        }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [id]);

  if (loadError) return <p className="text-red-400 p-8">{loadError}</p>;
  if (!run) return <p className="text-zinc-500 p-8">Loading run…</p>;

  return (
    <div className="space-y-8">
      <div className="pb-6 border-b border-zinc-800">
        <h1 className="text-3xl font-bold text-zinc-100">{run.topic}</h1>
        <div className="flex items-center gap-3 mt-4">
          <span className="capitalize text-sm text-zinc-400 font-medium bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-sm">
            {run.format} Run
          </span>
          <span className="text-sm font-semibold text-primary-500 bg-primary-900/20 border border-primary-900/50 px-3 py-1 rounded-sm">
            {STATUS_LABEL[status] ?? status}
          </span>
          {run.vertical && (() => {
            const vDef = VERTICALS.find((v) => v.key === run.vertical);
            return vDef ? (
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-sm">
                {vDef.displayName}
              </span>
            ) : null;
          })()}
        </div>
        
        {run.vertical_inputs && Object.keys(run.vertical_inputs).length > 0 && (
          <div className="mt-6 p-5 bg-zinc-900 border border-zinc-800 rounded-lg">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Submitted Context</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(run.vertical_inputs).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-zinc-500 capitalize font-medium">{k.replace(/_/g, ' ')}</dt>
                  <dd className="text-sm text-zinc-200 mt-0.5 break-words font-medium">{String(v)}</dd>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <AgentLog logs={logs} />

      {HITL_STATUSES.has(status) && hitlSummary && hitlStage && (
        <HitlModal
          runId={id}
          stage={hitlStage}
          stageSummary={hitlSummary}
          onApproved={() => {
            setHitlSummary(null);
            setHitlStage(null);
          }}
        />
      )}

      {status === "complete" && run.final_output && (
        <OutputPanel content={run.final_output} runId={id} />
      )}

      {status === "failed" && (
        <div className="border border-red-900 bg-red-950/20 rounded-lg p-5 text-red-400 font-medium">
          This run failed. Please check the agent logs above for details or contact support.
        </div>
      )}
    </div>
  );
}
