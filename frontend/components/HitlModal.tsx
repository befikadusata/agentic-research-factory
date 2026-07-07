"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { approveHitl } from "@/lib/api";

interface Props {
  runId: string;
  stage: string;
  stageSummary: string;
  onApproved: () => void;
}

const STAGE_COPY: Record<string, { title: string; description: string; cta: string; feedbackLabel: string }> = {
  awaiting_research_approval: {
    title: "Research Complete — Review Before Analysis",
    description: "Review the research below, optionally redirect the focus, then approve to continue to analysis.",
    cta: "Approve & Continue to Analysis",
    feedbackLabel: "Optional: redirect the focus for the analysis phase",
  },
  awaiting_analysis_approval: {
    title: "Analysis Complete — Review Before Writing",
    description: "Review the analysis below, optionally redirect the focus, then approve to begin writing.",
    cta: "Approve & Continue Writing",
    feedbackLabel: "Optional: redirect the focus for the writing phase",
  },
  awaiting_final_approval: {
    title: "Draft Complete — Review Before Publishing",
    description: "Review the final draft below, then approve to publish.",
    cta: "Approve & Publish",
    feedbackLabel: "Optional: add final notes or corrections",
  },
};

const DEFAULT_COPY = {
  title: "Review Required",
  description: "Review the output and approve to continue.",
  cta: "Approve & Continue",
  feedbackLabel: "Optional: add instructions",
};

export function HitlModal({ runId, stage, stageSummary, onApproved }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = STAGE_COPY[stage] ?? DEFAULT_COPY;

  const PROMPT_TEMPLATES = [
    "Focus more on pricing strategy.",
    "Clarify technical integration details.",
    "Expand on competitive differentiation.",
    "Maintain a conservative tone.",
  ];

  async function handleApprove() {
    setLoading(true);
    setError(null);
    try {
      await approveHitl(runId, instruction || undefined);
      onApproved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to approve");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-40"
          style={{ background: "var(--hitl-backdrop)" }}
        />
        <Dialog.Content
          className="ftm-hitl fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl
                     rounded-lg p-6 animate-hitl-enter shadow-hitl"
          style={{ background: "var(--hitl-surface)" }}
        >
          <header className="mb-4 flex items-center gap-2 border-b border-hitl/30 pb-3">
            <span className="text-hitl" aria-hidden>▮▮</span>
            <Dialog.Title asChild>
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-hitl">
                Checkpoint · {copy.title}
              </span>
            </Dialog.Title>
          </header>
          <Dialog.Description className="text-content-secondary text-sm mb-4">
            {copy.description}
          </Dialog.Description>

          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
            Draft summary
          </p>
          <div className="bg-surface-3 rounded-md p-4 max-h-64 overflow-y-auto text-sm mb-5 prose prose-invert prose-sm max-w-none text-content-secondary">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{stageSummary}</ReactMarkdown>
          </div>

          <label className="block text-[11px] font-semibold uppercase tracking-wide mb-1 text-content-muted">
            {copy.feedbackLabel}
          </label>
          <div className="flex flex-wrap gap-2 mb-2">
            {PROMPT_TEMPLATES.map((t) => (
              <button
                key={t}
                onClick={() => setInstruction((prev) => prev ? `${prev}\n${t}` : t)}
                className="text-xs bg-surface-3 hover:bg-surface-4 text-content-secondary px-2 py-1 rounded-sm border border-border-subtle transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g. Focus more on pricing strategy and enterprise segment"
            rows={3}
            className="w-full resize-none rounded-md bg-surface-3 p-3 text-sm mb-6 text-content
                       placeholder:text-content-muted outline-none ring-1 ring-border-subtle
                       focus:ring-2 focus:ring-hitl"
          />

          {error && <p className="text-feedback-error text-sm mb-3">{error}</p>}

          <div className="flex justify-end">
            <button
              onClick={handleApprove}
              disabled={loading}
              className="rounded-md bg-primary px-6 py-2 text-sm font-semibold text-primary-on
                         hover:bg-primary-hover transition-colors disabled:opacity-50
                         focus:outline-none focus:ring-2 focus:ring-border-focus focus:ring-offset-2
                         focus:ring-offset-surface-2"
            >
              {loading ? "Resuming…" : `${copy.cta} →`}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
