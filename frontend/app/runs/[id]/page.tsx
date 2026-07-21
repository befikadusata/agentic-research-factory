"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, LoaderCircle, Radar, RefreshCw } from "lucide-react";
import { createParser } from "eventsource-parser";
import { getRun, authHeaders } from "@/lib/api";
import { AgentLog } from "@/components/AgentLog";
import { AgentGraph } from "@/components/AgentGraph";
import { HitlModal } from "@/components/HitlModal";
import { OutputPanel } from "@/components/OutputPanel";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { MonitorDiffPanel } from "@/components/MonitorDiffPanel";
import { PlaybookIcon } from "@/components/PlaybookIcon";
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
  const [reviewOpen, setReviewOpen] = useState(true);
  const [reconnectKey, setReconnectKey] = useState(0);
  const [reconnecting, setReconnecting] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadRun = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const r = await getRun(id);
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
        setReviewOpen(true);
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Unable to load this run.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadRun();
  }, [loadRun]);

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
          setStreamError(null);
      } else if (parsed.type === "hitl_required") {
          setHitlStage(parsed.data.stage);
          setHitlSummary(parsed.data.summary);
          setStatus(parsed.data.stage as RunStatus);
          setReviewOpen(true);
      } else if (parsed.type === "complete") {
          setStatus("complete");
          getRun(id).then(setRun);
      } else if (parsed.type === "error") {
          setStatus("failed");
          setRunError(parsed.data.message ?? null);
          getRun(id).then(setRun);
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
        setStreamError(null);
        setReconnecting(false);

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
          setReconnecting(false);
          setStreamError("Live update stream disconnected. Reconnect to continue receiving progress updates.");
        }
      }
    })();

    return () => controller.abort();
  }, [id, reconnectKey]);

  if (loadError) return (
    <div role="alert" className="mx-auto max-w-lg rounded-lg border border-feedback-error/40 bg-feedback-error/10 p-6 text-content">
      <div className="flex items-start gap-3">
        <AlertTriangle size={20} className="mt-0.5 flex-none text-feedback-error" aria-hidden />
        <div>
          <h1 className="font-semibold">Unable to load this run</h1>
          <p className="mt-1 text-sm text-content-secondary">{loadError}</p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        <button onClick={loadRun} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-on hover:bg-primary-hover">
          <RefreshCw size={16} aria-hidden /> Retry
        </button>
        <Link href="/" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-content-secondary hover:bg-surface-2 hover:text-content">
          <ArrowLeft size={16} aria-hidden /> Back to runs
        </Link>
      </div>
    </div>
  );
  if (loading || !run) return (
    <div role="status" aria-label="Loading run" className="space-y-5 animate-pulse">
      <div className="h-9 w-2/3 rounded-md bg-surface-3" />
      <div className="h-6 w-64 rounded-md bg-surface-3" />
      <div className="h-44 rounded-xl bg-surface-2" />
      <span className="sr-only">Loading run…</span>
    </div>
  );

  const verticalDef = run.vertical ? VERTICALS.find((v) => v.key === run.vertical) ?? null : null;
  const statusGlyph = status ? AGENT_STATE_GLYPH[STATUS_TO_AGENT_STATE[status]] : "";

  return (
    <div className="space-y-8">
      <div className="pb-6 border-b border-border-subtle">
        <h1 className="text-2xl font-bold text-content break-words sm:text-3xl">{run.topic}</h1>
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <span className="capitalize text-sm text-content-secondary font-medium bg-surface-2 border border-border-subtle px-3 py-1 rounded-sm">
            {run.format} Run
          </span>
          <span aria-live="polite" className={`text-sm font-semibold px-3 py-1 rounded-sm ${status ? statusBadgeClass(status) : "text-content-muted bg-surface-2"}`}>
            {statusGlyph && <span aria-hidden>{statusGlyph} </span>}
            {status === null ? "…" : (STATUS_LABEL[status] ?? status)}
          </span>
          {verticalDef && (
            <span className={`inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider border px-3 py-1.5 rounded-sm ${verticalDef.accentClass}`}>
              <PlaybookIcon vertical={verticalDef.key} size={14} />
              {verticalDef.displayName}
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
        <div role="alert" className="flex flex-col items-start gap-3 text-content text-sm bg-hitl/10 border border-hitl/40 rounded-lg px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
          <span className="flex items-start gap-2"><AlertTriangle size={17} className="mt-0.5 flex-none text-hitl" aria-hidden /> {streamError}</span>
          <div className="flex gap-3">
            <button
              onClick={() => { setReconnecting(true); setReconnectKey((key) => key + 1); }}
              disabled={reconnecting}
              className="inline-flex min-h-11 items-center gap-2 rounded-md border border-hitl/40 px-3 py-2 text-sm font-semibold text-content transition-colors hover:bg-hitl/10 disabled:opacity-50"
            >
              <RefreshCw size={15} className={reconnecting ? "animate-spin" : ""} aria-hidden />
              {reconnecting ? "Reconnecting…" : "Reconnect"}
            </button>
            <button
              onClick={() => setStreamError(null)}
              className="min-h-11 px-2 text-sm text-content-secondary underline hover:text-content"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {status !== null && <AgentGraph status={status} failedAtStatus={run.failed_at_status} />}

      <AgentLog logs={logs} />

      {status !== null && HITL_STATUSES.has(status) && hitlSummary && hitlStage && !reviewOpen && (
        <div role="status" className="flex flex-col items-start gap-3 rounded-lg border border-hitl/40 bg-hitl/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-content">Your review is needed to continue</p>
            <p className="mt-1 text-sm text-content-secondary">The pipeline is paused safely at this checkpoint.</p>
          </div>
          <button onClick={() => setReviewOpen(true)} className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-on hover:bg-primary-hover">
            Open review
          </button>
        </div>
      )}

      {status !== null && HITL_STATUSES.has(status) && hitlSummary && hitlStage && reviewOpen && (
        <HitlModal
          runId={id}
          stage={hitlStage}
          stageSummary={hitlSummary}
          onDismiss={() => setReviewOpen(false)}
          onApproved={() => {
            setHitlSummary(null);
            setHitlStage(null);
            setReviewOpen(false);
            setResuming(true);
          }}
        />
      )}

      {resuming && (
        <div role="status" className="flex items-center gap-3 text-content text-sm bg-agent-thinking/10 border border-agent-thinking/40 rounded-lg px-4 py-3">
          <LoaderCircle size={17} className="animate-spin" aria-hidden />
          Pipeline resuming, waiting for the next stage to begin…
        </div>
      )}

      {status === "complete" && run.final_output && (
        <>
          <MonitorDiffPanel diff={run.metrics?.monitor_diff} />
          <ConfidenceBadge scores={run.metrics?.eval_scores} vertical={run.vertical} />
          {!run.monitor_id && (
            <div className="flex justify-end">
              <Link
                href={`/monitors?topic=${encodeURIComponent(run.topic)}&format=${run.format}&name=${encodeURIComponent(run.topic.slice(0, 60))}`}
                className="text-sm text-content-secondary hover:text-content border border-border-subtle hover:border-primary rounded-md px-4 py-2 flex items-center gap-2 transition-colors"
              >
                <Radar size={16} /> Save as monitor
              </Link>
            </div>
          )}
          <OutputPanel content={run.final_output} runId={id} />
        </>
      )}

      {status === "failed" && (
        <div role="alert" className="border border-feedback-error/40 bg-feedback-error/10 rounded-lg p-5 text-content font-medium">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="mt-0.5 flex-none text-feedback-error" aria-hidden />
            <div>
              <p>This run failed. Check the agent logs above for details.</p>
          {(runError ?? run.error_message) && (
            <p className="mt-2 text-sm font-normal text-content-secondary">{runError ?? run.error_message}</p>
          )}
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/new" className="inline-flex min-h-11 items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-on hover:bg-primary-hover">
              Start a new run
            </Link>
            <Link href="/" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-content-secondary hover:bg-surface-2 hover:text-content">
              <ArrowLeft size={16} aria-hidden /> Back to runs
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
