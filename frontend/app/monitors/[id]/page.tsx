"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Play, Pause, Zap, Trash2 } from "lucide-react";
import { getMonitor, getMonitorRuns, updateMonitor, runMonitorNow, deleteMonitor } from "@/lib/api";
import { RunCard } from "@/components/RunCard";
import { formatInterval, formatRelative, INTERVAL_PRESETS } from "@/lib/monitors";
import type { Monitor, Run } from "@/lib/types";

export default function MonitorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    getMonitor(id).then(setMonitor).catch((e) => setError(e.message));
    getMonitorRuns(id).then(setRuns).catch(() => {});
  }

  useEffect(load, [id]);

  async function toggleEnabled() {
    if (!monitor) return;
    setBusy(true);
    try {
      const updated = await updateMonitor(id, { enabled: !monitor.enabled });
      setMonitor(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function changeInterval(minutes: number) {
    setBusy(true);
    try {
      setMonitor(await updateMonitor(id, { interval_minutes: minutes }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runNow() {
    setBusy(true);
    try {
      const run = await runMonitorNow(id);
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed.");
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this monitor? Its past runs are kept.")) return;
    setBusy(true);
    try {
      await deleteMonitor(id);
      router.push("/monitors");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
      setBusy(false);
    }
  }

  if (error && !monitor) return <p role="alert" className="text-content p-8">{error}</p>;
  if (!monitor) return <p className="text-content-muted p-8">Loading monitor…</p>;

  return (
    <div className="max-w-4xl space-y-8">
      <div className="pb-6 border-b border-border-subtle">
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
            disabled={busy}
            className="bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-4 py-2 rounded-md flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            <Zap size={16} /> Run now
          </button>
          <button
            onClick={toggleEnabled}
            disabled={busy}
            className="bg-surface-3 hover:bg-surface-2 border border-border-subtle text-content text-sm font-medium px-4 py-2 rounded-md flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            {monitor.enabled ? <><Pause size={16} /> Pause</> : <><Play size={16} /> Resume</>}
          </button>
          <select
            value={monitor.interval_minutes}
            onChange={(e) => changeInterval(Number(e.target.value))}
            disabled={busy}
            className="bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-sm focus:border-primary outline-none disabled:opacity-50"
          >
            {INTERVAL_PRESETS.map((p) => (
              <option key={p.minutes} value={p.minutes}>{p.label}</option>
            ))}
            {!INTERVAL_PRESETS.some((p) => p.minutes === monitor.interval_minutes) && (
              <option value={monitor.interval_minutes}>{formatInterval(monitor.interval_minutes)}</option>
            )}
          </select>
          <button
            onClick={remove}
            disabled={busy}
            className="text-feedback-error hover:bg-feedback-error/10 text-sm font-medium px-3 py-2 rounded-md flex items-center gap-2 transition-colors disabled:opacity-50 sm:ml-auto"
          >
            <Trash2 size={16} /> Delete
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
        {runs.length === 0 ? (
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
    </div>
  );
}
