"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { ArrowLeft, LoaderCircle } from "lucide-react";
import { createRun } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { FormatSelector } from "@/components/FormatSelector";
import { FileUpload, type AttachedDoc } from "@/components/FileUpload";
import { VerticalSelector } from "@/components/VerticalSelector";
import { AuthLoadingState } from "@/components/AuthLoadingState";
import { useVerticals } from "@/lib/useVerticals";
import type { Vertical, OutputFormat } from "@/lib/types";

export default function NewRunPage() {
  const router = useRouter();
  const { data: session, status: authStatus } = useSession();
  const { activeId } = useWorkspace();
  const verticals = useVerticals();
  const [vertical, setVertical] = useState<Vertical | null>(null);
  const [verticalInputs, setVerticalInputs] = useState<Record<string, string>>({});
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState<OutputFormat>("report");
  const [doc, setDoc] = useState<AttachedDoc | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only a fully indexed doc is worth sending: a pending one has no chunks yet
  // and a failed one never will, so either would look attached but cite nothing.
  const docIds = doc?.status === "ready" ? [doc.docId] : [];
  const waitingOnIngest = doc?.status === "pending";

  useEffect(() => {
    if (!vertical) return;
    const refreshedDefinition = verticals.find((definition) => definition.key === vertical);
    if (!refreshedDefinition) {
      setVertical(null);
      setVerticalInputs({});
      setDoc(null);
      setFormat("report");
      return;
    }
    setFormat(refreshedDefinition.defaultFormat);
  }, [vertical, verticals]);

  useEffect(() => {
    if (authStatus === "unauthenticated") router.push("/");
  }, [authStatus, router]);

  if (authStatus === "loading") {
    return <AuthLoadingState title="Preparing your research workspace" description="Confirming your session before starting a new run." />;
  }
  if (!session) return null;

  const verticalDef = verticals.find((v) => v.key === vertical) ?? null;

  function handleVerticalChange(v: Vertical) {
    if (v === vertical) return;
    setVertical(v);
    setVerticalInputs({});
    setDoc(null);
    const def = verticals.find((vd) => vd.key === v);
    if (def) setFormat(def.defaultFormat);
  }

  function handleInputChange(field: string, value: string) {
    setVerticalInputs((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (verticalDef) {
      for (const [key, schema] of Object.entries(verticalDef.inputSchema)) {
        if (schema.required && !verticalInputs[key]?.trim()) {
          setError(`"${schema.label}" is required.`);
          return;
        }
      }
    }

    if (topic.trim().length < 3) {
      setError("Topic must be at least 3 characters.");
      return;
    }

    if (waitingOnIngest) {
      setError("Your PDF is still being indexed. Wait for it to finish, or remove it to start without it.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { id } = await createRun({
        topic: topic.trim(),
        format,
        doc_ids: docIds,
        workspace_id: activeId ?? undefined,
        vertical: vertical ?? undefined,
        vertical_inputs: Object.keys(verticalInputs).length ? verticalInputs : undefined,
      });
      router.push(`/runs/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create run");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <Link href="/" className="mb-5 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-content-secondary hover:text-content">
        <ArrowLeft size={16} aria-hidden /> Back to runs
      </Link>
      <h1 className="text-2xl font-bold mb-2 text-content sm:text-3xl">New Research Run</h1>
      <p className="text-content-secondary text-sm mb-8">
        Choose a playbook or start general research.
      </p>

      <form onSubmit={handleSubmit} aria-busy={loading} className="space-y-8">
        {/* Playbook selector */}
        <div>
          <label className="block text-sm font-semibold text-content-secondary mb-3">
            Playbook <span className="text-content-muted font-normal">(optional)</span>
          </label>
          <VerticalSelector value={vertical} onChange={handleVerticalChange} verticals={verticals} />
          {vertical && (
            <button
              type="button"
              onClick={() => { setVertical(null); setVerticalInputs({}); setFormat("report"); setDoc(null); }}
              className="mt-3 text-xs text-primary hover:text-primary-hover font-medium"
            >
              Clear playbook and use general research
            </button>
          )}
        </div>

        {/* Dynamic vertical inputs */}
        {verticalDef && Object.entries(verticalDef.inputSchema).length > 0 && (
          <div className="space-y-5 border border-border-subtle rounded-lg p-5 bg-surface-2">
            <p className="text-xs text-content-secondary uppercase tracking-wider font-bold">
              {verticalDef.displayName} — Structured Context
            </p>
            {Object.entries(verticalDef.inputSchema).map(([key, schema]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-content-secondary mb-1.5">
                  {schema.label}{" "}
                  {schema.required ? (
                    <span className="text-primary">*</span>
                  ) : (
                    <span className="text-content-muted font-normal">(optional)</span>
                  )}
                </label>
                {schema.type === "select" ? (
                  <select
                    value={verticalInputs[key] ?? ""}
                    onChange={(e) => handleInputChange(key, e.target.value)}
                    className="w-full bg-surface-3 border border-border-subtle rounded-md px-3 py-2 text-sm text-content focus:outline-none focus:border-primary transition-colors"
                  >
                    <option value="">{schema.placeholder}</option>
                    {schema.options?.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={schema.type === "url" ? "url" : "text"}
                    value={verticalInputs[key] ?? ""}
                    onChange={(e) => handleInputChange(key, e.target.value)}
                    placeholder={schema.placeholder}
                    className="w-full bg-surface-3 border border-border-subtle rounded-md px-3 py-2 text-sm text-content placeholder:text-content-muted focus:outline-none focus:border-primary transition-colors"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Research topic */}
        <div>
          <label className="block text-sm font-semibold text-content-secondary mb-3">
            Research Topic
          </label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Competitive landscape for Notion in project management, 2025"
            className="w-full bg-surface-3 border border-border-subtle rounded-md p-3 text-sm resize-none h-24 text-content placeholder:text-content-muted focus:outline-none focus:border-primary transition-colors"
            required
            minLength={3}
            maxLength={500}
          />
          <p className="text-content-muted text-xs mt-1.5">{topic.length}/500</p>
        </div>

        {/* Output format */}
        <div>
          <label className="block text-sm font-semibold text-content-secondary mb-3">Output Format</label>
          <FormatSelector value={format} onChange={setFormat} />
        </div>

        {/* Upload reference PDF */}
        <div>
          <label className="block text-sm font-semibold text-content-secondary mb-3">
            Upload Reference PDF <span className="text-content-muted font-normal">(optional)</span>
          </label>
          <FileUpload
            key={vertical ?? "general"}
            workspaceId={activeId}
            onChange={setDoc}
          />
        </div>

        {error && <p role="alert" className="text-content text-sm bg-feedback-error/10 border border-feedback-error/40 p-3 rounded-md">{error}</p>}

        {loading && (
          <p role="status" className="flex items-center gap-2 rounded-md border border-agent-thinking/40 bg-agent-thinking/10 p-3 text-sm text-content-secondary">
            <LoaderCircle size={16} className="animate-spin" aria-hidden />
            Creating your run and preparing the research pipeline…
          </p>
        )}

        <button
          type="submit"
          disabled={loading || waitingOnIngest}
          className="w-full bg-primary hover:bg-primary-hover text-primary-on font-semibold py-3 rounded-md disabled:opacity-50 transition-colors duration-base"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <LoaderCircle size={17} className="animate-spin" aria-hidden /> Starting research…
            </span>
          ) : waitingOnIngest ? (
            "Waiting for your PDF to finish indexing…"
          ) : vertical ? `Start ${verticalDef?.displayName ?? "Research"}` : "Start Research"}
        </button>
      </form>
    </div>
  );
}
