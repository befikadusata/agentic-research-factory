"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";
import { FormatSelector } from "@/components/FormatSelector";
import { FileUpload } from "@/components/FileUpload";
import { VerticalSelector } from "@/components/VerticalSelector";
import { VERTICALS, type Vertical, type OutputFormat } from "@/lib/types";

export default function NewRunPage() {
  const router = useRouter();
  const [vertical, setVertical] = useState<Vertical | null>(null);
  const [verticalInputs, setVerticalInputs] = useState<Record<string, string>>({});
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState<OutputFormat>("report");
  const [docIds, setDocIds] = useState<string[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const verticalDef = VERTICALS.find((v) => v.key === vertical) ?? null;

  function handleVerticalChange(v: Vertical) {
    setVertical(v);
    setVerticalInputs({});
    const def = VERTICALS.find((vd) => vd.key === v);
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

    setLoading(true);
    setError(null);

    try {
      const { id } = await createRun({
        topic: topic.trim(),
        format,
        doc_ids: docIds,
        vertical: vertical ?? undefined,
        vertical_inputs: Object.keys(verticalInputs).length ? verticalInputs : undefined,
      });
      router.push(`/runs/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create run");
      setLoading(false);
    }
  }

  function handleUploaded(docId: string, filename: string) {
    setDocIds((prev) => [...prev, docId]);
    setUploadedFiles((prev) => [...prev, filename]);
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold mb-2 text-zinc-100">New Research Run</h1>
      <p className="text-zinc-400 text-sm mb-8">
        Choose a playbook or start general research.
      </p>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Playbook selector */}
        <div>
          <label className="block text-sm font-semibold text-zinc-300 mb-3">
            Playbook <span className="text-zinc-500 font-normal">(optional)</span>
          </label>
          <VerticalSelector value={vertical} onChange={handleVerticalChange} />
          {vertical && (
            <button
              type="button"
              onClick={() => { setVertical(null); setVerticalInputs({}); }}
              className="mt-3 text-xs text-primary-500 hover:text-primary-400 font-medium"
            >
              Clear playbook and use general research
            </button>
          )}
        </div>

        {/* Dynamic vertical inputs */}
        {verticalDef && Object.entries(verticalDef.inputSchema).length > 0 && (
          <div className="space-y-5 border border-zinc-800 rounded-lg p-5 bg-zinc-900/50">
            <p className="text-xs text-zinc-400 uppercase tracking-wider font-bold">
              {verticalDef.displayName} — Structured Context
            </p>
            {Object.entries(verticalDef.inputSchema).map(([key, schema]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  {schema.label}{" "}
                  {schema.required ? (
                    <span className="text-primary-500">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(optional)</span>
                  )}
                </label>
                {schema.type === "select" ? (
                  <select
                    value={verticalInputs[key] ?? ""}
                    onChange={(e) => handleInputChange(key, e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-primary-500 transition-colors"
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
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-primary-500 transition-colors"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Research topic */}
        <div>
          <label className="block text-sm font-semibold text-zinc-300 mb-3">
            Research Topic
          </label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Competitive landscape for Notion in project management, 2025"
            className="w-full bg-zinc-950 border border-zinc-700 rounded-md p-3 text-sm resize-none h-24 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-primary-500 transition-colors"
            required
            minLength={3}
            maxLength={500}
          />
          <p className="text-zinc-600 text-xs mt-1.5">{topic.length}/500</p>
        </div>

        {/* Output format */}
        <div>
          <label className="block text-sm font-semibold text-zinc-300 mb-3">Output Format</label>
          <FormatSelector value={format} onChange={setFormat} />
        </div>

        {/* Upload reference PDF */}
        <div>
          <label className="block text-sm font-semibold text-zinc-300 mb-3">
            Upload Reference PDF <span className="text-zinc-500 font-normal">(optional)</span>
          </label>
          <FileUpload onUploaded={handleUploaded} />
          {uploadedFiles.length > 0 && (
            <ul className="mt-3 space-y-1">
              {uploadedFiles.map((f, i) => (
                <li key={i} className="text-cta text-sm font-medium">✓ {f}</li>
              ))}
            </ul>
          )}
        </div>

        {error && <p className="text-red-400 text-sm bg-red-900/20 p-3 rounded-md">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-cta hover:bg-green-600 text-white font-semibold py-3 rounded-lg disabled:opacity-50 transition-colors duration-200"
        >
          {loading ? "Starting…" : vertical ? `Start ${verticalDef?.displayName ?? "Research"}` : "Start Research"}
        </button>
      </form>
    </div>
  );
}
