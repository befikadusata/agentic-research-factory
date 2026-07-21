"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { LoaderCircle, Plus } from "lucide-react";
import { getMonitors, createMonitor } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { MonitorCard } from "@/components/MonitorCard";
import { FormatSelector } from "@/components/FormatSelector";
import { CardListSkeleton, LoadError } from "@/components/ListState";
import { INTERVAL_PRESETS } from "@/lib/monitors";
import type { Monitor, OutputFormat } from "@/lib/types";

export default function MonitorsPage() {
  const { status } = useSession();
  const { activeId, active } = useWorkspace();
  const params = useSearchParams();

  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Prefill from query params (the run detail page's "Save as monitor" link).
  const prefillTopic = params.get("topic") ?? "";
  const [showForm, setShowForm] = useState(!!prefillTopic);
  const [name, setName] = useState(params.get("name") ?? "");
  const [topic, setTopic] = useState(prefillTopic);
  const [format, setFormat] = useState<OutputFormat>((params.get("format") as OutputFormat) || "report");
  const [interval, setInterval] = useState(1440);
  const [notify, setNotify] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const nameInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    if (status !== "authenticated" || !activeId) return;
    setLoading(true);
    setError(null);
    getMonitors(activeId)
      .then(setMonitors)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status, activeId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (showForm) nameInputRef.current?.focus();
  }, [showForm]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await createMonitor({
        name: name.trim(),
        topic: topic.trim(),
        format,
        workspace_id: activeId ?? undefined,
        interval_minutes: interval,
        enabled: true,
        notify_channel: notify.trim() || null,
      });
      setName("");
      setTopic("");
      setNotify("");
      setShowForm(false);
      setAnnouncement(`${created.name} monitor created.`);
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create monitor.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="flex flex-col items-start gap-4 mb-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-content">Monitors</h1>
          <p className="text-sm text-content-muted mt-1">
            {active ? active.name : "Recurring research that alerts you when something changes"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          aria-expanded={showForm}
          aria-controls="new-monitor-form"
          className="min-h-11 bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base flex items-center gap-2"
        >
          {!showForm && <Plus size={16} aria-hidden />}
          {showForm ? "Cancel" : "New Monitor"}
        </button>
      </div>

      <p className="sr-only" aria-live="polite">{announcement}</p>

      {showForm && (
        <form
          id="new-monitor-form"
          onSubmit={submit}
          aria-busy={submitting}
          className="bg-surface-2 border border-border-subtle rounded-lg p-4 mb-8 space-y-5 sm:p-6"
        >
          <div>
            <label htmlFor="monitor-name" className="block text-sm font-medium text-content-secondary mb-1">Name</label>
            <input
              ref={nameInputRef}
              id="monitor-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={255}
              placeholder="e.g. Nvidia earnings watch"
              className="min-h-11 w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none"
            />
          </div>
          <div>
            <label htmlFor="monitor-topic" className="block text-sm font-medium text-content-secondary mb-1">Research topic</label>
            <textarea
              id="monitor-topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              required
              minLength={3}
              maxLength={500}
              rows={2}
              placeholder="What should this monitor research each run?"
              className="w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-content-secondary mb-2">Format</label>
            <FormatSelector value={format} onChange={setFormat} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="monitor-frequency" className="block text-sm font-medium text-content-secondary mb-1">Frequency</label>
              <select
                id="monitor-frequency"
                value={interval}
                onChange={(e) => setInterval(Number(e.target.value))}
                className="min-h-11 w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none"
              >
                {INTERVAL_PRESETS.map((p) => (
                  <option key={p.minutes} value={p.minutes}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="monitor-notify" className="block text-sm font-medium text-content-secondary mb-1">
                Alert email or webhook <span className="text-content-muted font-normal">(optional)</span>
              </label>
              <input
                id="monitor-notify"
                type="text"
                value={notify}
                onChange={(e) => setNotify(e.target.value)}
                placeholder="you@example.com or https://hooks.slack.com/…"
                className="min-h-11 w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
          {formError && (
            <p role="alert" className="text-content text-sm bg-feedback-error/10 border border-feedback-error/40 rounded-md px-3 py-2">
              {formError}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="min-h-11 bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <span className="flex items-center gap-2"><LoaderCircle size={16} className="animate-spin" aria-hidden /> Creating…</span>
            ) : "Create Monitor"}
          </button>
        </form>
      )}

      {loading && <CardListSkeleton label="Loading monitors" count={2} />}
      {!loading && error && (
        <LoadError title="Monitors couldn’t be loaded" message={error} onRetry={load} />
      )}
      {!loading && !error && monitors.length === 0 && !showForm && (
        <div className="border-2 border-dashed border-border-subtle rounded-lg px-6 py-12 text-center text-content-muted sm:p-16">
          <p className="text-lg mb-4">No monitors yet.</p>
          <button onClick={() => setShowForm(true)} className="text-primary hover:text-primary-hover font-medium">
            Create your first monitor →
          </button>
        </div>
      )}

      <div className="space-y-4">
        {monitors.map((m) => (
          <MonitorCard key={m.id} monitor={m} />
        ))}
      </div>
    </div>
  );
}
