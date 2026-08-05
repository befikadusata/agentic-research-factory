"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { LoaderCircle, Plus } from "lucide-react";
import { getMonitors, createMonitor } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { MonitorCard } from "@/components/MonitorCard";
import { FormatSelector } from "@/components/FormatSelector";
import { VerticalSelector } from "@/components/VerticalSelector";
import { CardListSkeleton, LoadError } from "@/components/ListState";
import { INTERVAL_PRESETS } from "@/lib/monitors";
import { useVerticals } from "@/lib/useVerticals";
import type { Monitor, OutputFormat, Vertical } from "@/lib/types";

/** Structured inputs arrive from the "Save as monitor" link as one JSON param.
 *  Anything unparseable is dropped rather than thrown: a mangled link should
 *  still open an empty form, not a broken page. */
function parseVerticalInputs(raw: string | null): Record<string, string> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, string>)
      : {};
  } catch {
    return {};
  }
}

export default function MonitorsPage() {
  const { status } = useSession();
  const { activeId, active } = useWorkspace();
  const params = useSearchParams();

  const verticals = useVerticals();

  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Prefill from query params (the run detail page's "Save as monitor" link).
  const prefillTopic = params.get("topic") ?? "";
  const [showForm, setShowForm] = useState(!!prefillTopic);
  const [name, setName] = useState(params.get("name") ?? "");
  const [topic, setTopic] = useState(prefillTopic);
  const [format, setFormat] = useState<OutputFormat>((params.get("format") as OutputFormat) || "report");
  const [vertical, setVertical] = useState<Vertical | null>(
    (params.get("vertical") as Vertical) || null,
  );
  const [verticalInputs, setVerticalInputs] = useState<Record<string, string>>(() =>
    parseVerticalInputs(params.get("vertical_inputs")),
  );
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

  // Drop a playbook the backend doesn't offer — it can only have come from a
  // hand-edited or stale link, and the server would reject the create anyway.
  useEffect(() => {
    if (vertical && !verticals.some((v) => v.key === vertical)) {
      setVertical(null);
      setVerticalInputs({});
    }
  }, [vertical, verticals]);

  const verticalDef = verticals.find((v) => v.key === vertical) ?? null;

  function handleVerticalChange(v: Vertical) {
    if (v === vertical) return;
    setVertical(v);
    setVerticalInputs({});
    const def = verticals.find((vd) => vd.key === v);
    if (def) setFormat(def.defaultFormat);
  }

  function clearVertical() {
    setVertical(null);
    setVerticalInputs({});
    setFormat("report");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();

    // Mirrors validate_vertical_inputs on the backend, which 422s on a missing
    // required field. Checking here names the field instead.
    if (verticalDef) {
      for (const [key, schema] of Object.entries(verticalDef.inputSchema)) {
        if (schema.required && !verticalInputs[key]?.trim()) {
          setFormError(`"${schema.label}" is required.`);
          return;
        }
      }
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const created = await createMonitor({
        name: name.trim(),
        topic: topic.trim(),
        format,
        workspace_id: activeId ?? undefined,
        vertical: vertical ?? undefined,
        vertical_inputs: Object.keys(verticalInputs).length ? verticalInputs : undefined,
        interval_minutes: interval,
        enabled: true,
        notify_channel: notify.trim() || null,
      });
      setName("");
      setTopic("");
      setNotify("");
      clearVertical();
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
            <label className="block text-sm font-medium text-content-secondary mb-2">
              Playbook <span className="text-content-muted font-normal">(optional)</span>
            </label>
            <VerticalSelector value={vertical} onChange={handleVerticalChange} verticals={verticals} />
            {vertical && (
              <button
                type="button"
                onClick={clearVertical}
                className="mt-3 text-xs text-primary hover:text-primary-hover font-medium"
              >
                Clear playbook and use general research
              </button>
            )}
          </div>

          {verticalDef && Object.entries(verticalDef.inputSchema).length > 0 && (
            <div className="space-y-5 border border-border-subtle rounded-lg p-4 bg-surface-1 sm:p-5">
              <p className="text-xs text-content-secondary uppercase tracking-wider font-bold">
                {verticalDef.displayName} — Structured Context
              </p>
              {Object.entries(verticalDef.inputSchema).map(([key, schema]) => (
                <div key={key}>
                  <label
                    htmlFor={`monitor-vertical-${key}`}
                    className="block text-sm font-medium text-content-secondary mb-1.5"
                  >
                    {schema.label}{" "}
                    {schema.required ? (
                      <span className="text-primary">*</span>
                    ) : (
                      <span className="text-content-muted font-normal">(optional)</span>
                    )}
                  </label>
                  {schema.type === "select" ? (
                    <select
                      id={`monitor-vertical-${key}`}
                      value={verticalInputs[key] ?? ""}
                      onChange={(e) =>
                        setVerticalInputs((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                      className="min-h-11 w-full bg-surface-3 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm focus:border-primary outline-none"
                    >
                      <option value="">{schema.placeholder}</option>
                      {schema.options?.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={`monitor-vertical-${key}`}
                      type={schema.type === "url" ? "url" : "text"}
                      value={verticalInputs[key] ?? ""}
                      onChange={(e) =>
                        setVerticalInputs((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                      placeholder={schema.placeholder}
                      className="min-h-11 w-full bg-surface-3 border border-border-subtle rounded-md px-3 py-2 text-content text-base sm:text-sm placeholder:text-content-muted focus:border-primary outline-none"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

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
