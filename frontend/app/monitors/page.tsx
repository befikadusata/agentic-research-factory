"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { getMonitors, createMonitor } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { MonitorCard } from "@/components/MonitorCard";
import { FormatSelector } from "@/components/FormatSelector";
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

  function load() {
    if (status !== "authenticated" || !activeId) return;
    setLoading(true);
    setError(null);
    getMonitors(activeId)
      .then(setMonitors)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [status, activeId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createMonitor({
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
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create monitor.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-content">Monitors</h1>
          <p className="text-sm text-content-muted mt-1">
            {active ? active.name : "Recurring research that alerts you when something changes"}
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base"
        >
          {showForm ? "Cancel" : "New Monitor"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={submit} className="bg-surface-2 border border-border-subtle rounded-lg p-6 mb-8 space-y-5">
          <div>
            <label className="block text-sm font-medium text-content-secondary mb-1">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={255}
              placeholder="e.g. Nvidia earnings watch"
              className="w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-sm focus:border-primary outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-content-secondary mb-1">Research topic</label>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              required
              minLength={3}
              maxLength={500}
              rows={2}
              placeholder="What should this monitor research each run?"
              className="w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-sm focus:border-primary outline-none resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-content-secondary mb-2">Format</label>
            <FormatSelector value={format} onChange={setFormat} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-content-secondary mb-1">Frequency</label>
              <select
                value={interval}
                onChange={(e) => setInterval(Number(e.target.value))}
                className="w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-sm focus:border-primary outline-none"
              >
                {INTERVAL_PRESETS.map((p) => (
                  <option key={p.minutes} value={p.minutes}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-content-secondary mb-1">
                Alert email or webhook <span className="text-content-muted font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={notify}
                onChange={(e) => setNotify(e.target.value)}
                placeholder="you@example.com or https://hooks.slack.com/…"
                className="w-full bg-surface-1 border border-border-subtle rounded-md px-3 py-2 text-content text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
          {formError && (
            <p className="text-content text-sm bg-feedback-error/10 border border-feedback-error/40 rounded-md px-3 py-2">
              {formError}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create Monitor"}
          </button>
        </form>
      )}

      {loading && <p className="text-content-muted">Loading monitors…</p>}
      {error && <p className="text-content bg-feedback-error/10 border border-feedback-error/40 p-4 rounded-lg">{error}</p>}
      {!loading && !error && monitors.length === 0 && !showForm && (
        <div className="border-2 border-dashed border-border-subtle rounded-lg p-16 text-center text-content-muted">
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
