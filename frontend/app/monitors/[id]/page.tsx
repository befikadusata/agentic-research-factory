"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowLeft, LoaderCircle, Play, Pause, Zap, Trash2, X } from "lucide-react";
import { getMonitor, getMonitorRuns, updateMonitor, runMonitorNow, deleteMonitor } from "@/lib/api";
import { RunCard } from "@/components/RunCard";
import { CardListSkeleton, LoadError } from "@/components/ListState";
import { formatInterval, formatRelative, INTERVAL_PRESETS } from "@/lib/monitors";
import type { Monitor, Run } from "@/lib/types";

export default function MonitorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [loadingMonitor, setLoadingMonitor] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [busy, setBusy] = useState<"run" | "toggle" | "interval" | "delete" | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  const loadMonitor = useCallback(() => {
    setLoadingMonitor(true);
    setError(null);
    getMonitor(id)
      .then(setMonitor)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMonitor(false));
  }, [id]);

  const loadRuns = useCallback(() => {
    setLoadingRuns(true);
    setRunsError(null);
    getMonitorRuns(id)
      .then(setRuns)
      .catch((e) => setRunsError(e.message))
      .finally(() => setLoadingRuns(false));
  }, [id]);

  useEffect(() => {
    loadMonitor();
    loadRuns();
  }, [loadMonitor, loadRuns]);

  async function toggleEnabled() {
    if (!monitor) return;
    setBusy("toggle");
    setError(null);
    try {
      const updated = await updateMonitor(id, { enabled: !monitor.enabled });
      setMonitor(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusy(null);
    }
  }

  async function changeInterval(minutes: number) {
    setBusy("interval");
    setError(null);
    try {
      setMonitor(await updateMonitor(id, { interval_minutes: minutes }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusy(null);
    }
  }

  async function runNow() {
    setBusy("run");
    setError(null);
    try {
      const run = await runMonitorNow(id);
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed.");
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("delete");
    setError(null);
    try {
      await deleteMonitor(id);
      router.push("/monitors");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
      setBusy(null);
      setShowDelete(false);
    }
  }

  if (loadingMonitor && !monitor) {
    return (
      <div className="max-w-4xl" role="status" aria-label="Loading monitor">
        <div aria-hidden className="animate-pulse space-y-5">
          <div className="h-4 w-28 rounded bg-surface-3" />
          <div className="h-8 w-2/3 rounded bg-surface-3" />
          <div className="h-4 w-full max-w-xl rounded bg-surface-2" />
          <div className="h-11 w-80 max-w-full rounded bg-surface-2" />
        </div>
        <span className="sr-only">Loading monitor</span>
      </div>
    );
  }
  if (error && !monitor) {
    return (
      <div className="max-w-4xl space-y-6">
        <Link href="/monitors" className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-content-secondary hover:text-primary">
          <ArrowLeft size={16} aria-hidden /> Back to monitors
        </Link>
        <LoadError title="This monitor couldn’t be loaded" message={error} onRetry={loadMonitor} />
      </div>
    );
  }
  if (!monitor) return null;

  return (
    <div className="max-w-4xl space-y-8">
      <div className="pb-6 border-b border-border-subtle">
        <Link href="/monitors" className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-content-secondary hover:text-primary">
          <ArrowLeft size={16} aria-hidden /> Back to monitors
        </Link>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:justify-between sm:gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-content sm:text-3xl">{monitor.name}</h1>
            <p className="text-content-secondary mt-2">{monitor.topic}</p>
          </div>
          <span
            className={`text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-sm whitespace-nowrap ${
              monitor.enabled
                ? "text-feedback-success bg-feedback-success/10"
                : "text-content-muted bg-surface-3"
            }`}
          >
            {monitor.enabled ? "Active" : "Paused"}
          </span>
        </div>

        <div className="flex items-center gap-4 mt-4 text-sm text-content-muted flex-wrap">
          <span className="capitalize">{monitor.format} · {formatInterval(monitor.interval_minutes)}</span>
          {monitor.enabled && <span>Next run {formatRelative(monitor.next_run_at)}</span>}
          {monitor.notify_channel && <span>Alerts → {monitor.notify_channel}</span>}
        </div>

        <div className="flex items-center gap-3 mt-6 flex-wrap">
          <button
            onClick={runNow}
            disabled={busy !== null}
            className="min-h-11 bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-4 py-2 rounded-md flex items-center gap-2 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "run" ? <LoaderCircle size={16} className="animate-spin" aria-hidden /> : <Zap size={16} aria-hidden />}
            {busy === "run" ? "Starting…" : "Run now"}
          </button>
          <button
            onClick={toggleEnabled}
            disabled={busy !== null}
            className="min-h-11 bg-surface-3 hover:bg-surface-2 border border-border-subtle text-content text-sm font-medium px-4 py-2 rounded-md flex items-center gap-2 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "toggle" ? (
              <><LoaderCircle size={16} className="animate-spin" aria-hidden /> Updating…</>
            ) : monitor.enabled ? (
              <><Pause size={16} aria-hidden /> Pause</>
            ) : (
              <><Play size={16} aria-hidden /> Resume</>
            )}
          </button>
          <label htmlFor="monitor-detail-frequency" className="sr-only">Run frequency</label>
          <select
            id="monitor-detail-frequency"
            value={monitor.interval_minutes}
            onChange={(e) => changeInterval(Number(e.target.value))}
            disabled={busy !== null}
            className="min-h-11 bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            {INTERVAL_PRESETS.map((p) => (
              <option key={p.minutes} value={p.minutes}>{p.label}</option>
            ))}
            {!INTERVAL_PRESETS.some((p) => p.minutes === monitor.interval_minutes) && (
              <option value={monitor.interval_minutes}>{formatInterval(monitor.interval_minutes)}</option>
            )}
          </select>
          <button
            type="button"
            onClick={() => setShowDelete(true)}
            disabled={busy !== null}
            className="min-h-11 text-feedback-error hover:bg-feedback-error/10 text-sm font-medium px-3 py-2 rounded-md flex items-center gap-2 transition-colors disabled:cursor-not-allowed disabled:opacity-50 sm:ml-auto"
          >
            <Trash2 size={16} aria-hidden /> Delete
          </button>
        </div>

        {error && (
          <p role="alert" className="text-content text-sm bg-feedback-error/10 border border-feedback-error/40 rounded-md px-3 py-2 mt-4">
            {error}
          </p>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-content mb-4">Run history</h2>
        {loadingRuns ? (
          <CardListSkeleton label="Loading monitor run history" count={2} />
        ) : runsError ? (
          <LoadError title="Run history couldn’t be loaded" message={runsError} onRetry={loadRuns} />
        ) : runs.length === 0 ? (
          <div className="border-2 border-dashed border-border-subtle rounded-lg px-6 py-10 text-center text-content-muted sm:p-12">
            No runs yet. The first run establishes a baseline; later runs are compared against it.
          </div>
        ) : (
          <div className="space-y-4">
            {runs.map((run) => (
              <RunCard key={run.id} run={run} />
            ))}
          </div>
        )}
      </div>

      <Dialog.Root open={showDelete} onOpenChange={(open) => { if (busy !== "delete") setShowDelete(open); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border-subtle bg-surface-2 p-5 shadow-xl sm:p-6">
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1">
                <Dialog.Title className="text-lg font-semibold text-content">Delete this monitor?</Dialog.Title>
                <Dialog.Description className="mt-2 text-sm leading-6 text-content-secondary">
                  {monitor.name} will stop running on its schedule. Its past research runs will remain available.
                </Dialog.Description>
              </div>
              <Dialog.Close asChild>
                <button
                  type="button"
                  disabled={busy === "delete"}
                  aria-label="Close delete confirmation"
                  className="-m-2 flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-3 hover:text-content disabled:opacity-50"
                >
                  <X size={18} aria-hidden />
                </button>
              </Dialog.Close>
            </div>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Dialog.Close asChild>
                <button
                  type="button"
                  disabled={busy === "delete"}
                  className="min-h-11 rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-content transition-colors hover:bg-surface-3 disabled:opacity-50"
                >
                  Keep monitor
                </button>
              </Dialog.Close>
              <button
                type="button"
                onClick={remove}
                disabled={busy === "delete"}
                className="min-h-11 rounded-md bg-feedback-error px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === "delete" ? (
                  <span className="flex items-center justify-center gap-2"><LoaderCircle size={16} className="animate-spin" aria-hidden /> Deleting…</span>
                ) : "Delete monitor"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
