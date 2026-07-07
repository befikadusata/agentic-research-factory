"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { createParser } from "eventsource-parser";
import { getRun, authHeaders } from "@/lib/api";
import { AgentLog } from "@/components/AgentLog";
import { AgentGraph } from "@/components/AgentGraph";
import { HitlModal } from "@/components/HitlModal";
import { OutputPanel } from "@/components/OutputPanel";
import type { RunDetail, LogEntry, RunStatus } from "@/lib/types";
import { VERTICALS, AGENT_STATE_GLYPH, STATUS_TO_AGENT_STATE, statusBadgeClass } from "@/lib/types";

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
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    getRun(id)
      .then((r) => {
        setRun(r);
        setLogs(r.logs ?? []);
        setStatus((prev) => (prev === null ? r.status : prev));
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
    const controller = new AbortController();

    const handleEvent = (data: string) => {
      if (data === "heartbeat") return;
      const parsed = JSON.parse(data);
      if (parsed.type === "log") {
          setLogs((prev) => [...prev, parsed.data]);
      } else if (parsed.type === "status") {
          setStatus(parsed.data.status);
          setResuming(false);
      } else if (parsed.type === "hitl_required") {
          setHitlStage(parsed.data.stage);
          setHitlSummary(parsed.data.summary);
          setStatus(parsed.data.stage as RunStatus);
      } else if (parsed.type === "complete") {
          setStatus("complete");
          getRun(id).then(setRun);
      } else if (parsed.type === "error") {
          setStatus("failed");
          setRunError(parsed.data.message ?? null);
      }
    };

    (async () => {
      // Native EventSource can't send an Authorization header, so the stream
      // is read via fetch (same bearer-token auth as every other backend call)
      // and parsed by hand instead.
      try {
        const headers = await authHeaders();
        const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/runs/${id}/stream`, {
          headers,
          signal: controller.signal,
        });
        if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

        const parser = createParser({ onEvent: (e) => handleEvent(e.data) });
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          parser.feed(decoder.decode(value, { stream: true }));
        }
      } catch {
        if (!controller.signal.aborted) {
          setStreamError("Live update stream disconnected. Refresh the page to reconnect.");
        }
      }
    })();

    return () => controller.abort();
  }, [id]);

  if (loadError) return <p className="text-content p-8">{loadError}</p>;
  if (!run) return <p className="text-content-muted p-8">Loading run…</p>;

  const verticalDef = run.vertical ? VERTICALS.find((v) => v.key === run.vertical) ?? null : null;
  const statusGlyph = status ? AGENT_STATE_GLYPH[STATUS_TO_AGENT_STATE[status]] : "";

  return (
    <div className="space-y-8">
      <div className="pb-6 border-b border-border-subtle">
        <h1 className="text-3xl font-bold text-content">{run.topic}</h1>
        <div className="flex items-center gap-3 mt-4">
          <span className="capitalize text-sm text-content-secondary font-medium bg-surface-2 border border-border-subtle px-3 py-1 rounded-sm">
            {run.format} Run
          </span>
          <span className={`text-sm font-semibold px-3 py-1 rounded-sm ${status ? statusBadgeClass(status) : "text-content-muted bg-surface-2"}`}>
            {statusGlyph && <span aria-hidden>{statusGlyph} </span>}
            {status === null ? "…" : (STATUS_LABEL[status] ?? status)}
          </span>
          {verticalDef && (
            <span className={`text-xs font-bold uppercase tracking-wider border px-3 py-1.5 rounded-sm ${verticalDef.accentClass}`}>
              {verticalDef.icon} {verticalDef.displayName}
            </span>
          )}
        </div>

        {run.vertical_inputs && Object.keys(run.vertical_inputs).length > 0 && (
          <div className="mt-6 p-5 bg-surface-2 border border-border-subtle rounded-lg">
            <h3 className="text-xs font-bold text-content-secondary uppercase tracking-wider mb-3">Submitted Context</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(run.vertical_inputs).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-content-muted font-medium">
                    {verticalDef?.inputSchema[k]?.label ?? k.replace(/_/g, " ")}
                  </dt>
                  <dd className="text-sm text-content mt-0.5 break-words font-medium">{String(v)}</dd>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {streamError && (
        <div className="flex items-center justify-between gap-2 text-content text-sm bg-hitl/10 border border-hitl/40 rounded-lg px-4 py-3">
          <span>⚠ {streamError}</span>
          <button
            onClick={() => setStreamError(null)}
            className="text-content-secondary hover:text-content text-xs underline flex-shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {status !== null && <AgentGraph status={status} />}

      <AgentLog logs={logs} />

      {status !== null && HITL_STATUSES.has(status) && hitlSummary && hitlStage && (
        <HitlModal
          runId={id}
          stage={hitlStage}
          stageSummary={hitlSummary}
          onApproved={() => {
            setHitlSummary(null);
            setHitlStage(null);
            setResuming(true);
          }}
        />
      )}

      {resuming && (
        <div className="flex items-center gap-3 text-content text-sm bg-agent-thinking/10 border border-agent-thinking/40 rounded-lg px-4 py-3">
          <span className="inline-block animate-spin">⟳</span>
          Pipeline resuming, waiting for the next stage to begin…
        </div>
      )}

      {status === "complete" && run.final_output && (
        <OutputPanel content={run.final_output} runId={id} />
      )}

      {status === "failed" && (
        <div className="border border-feedback-error/40 bg-feedback-error/10 rounded-lg p-5 text-content font-medium">
          This run failed. Check the agent logs above for details.
          {(runError ?? run.error_message) && (
            <p className="mt-2 text-sm font-normal text-content-secondary">{runError ?? run.error_message}</p>
          )}
        </div>
      )}
    </div>
  );
}
