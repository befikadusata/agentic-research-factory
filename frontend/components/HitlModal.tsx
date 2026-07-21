"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { LoaderCircle, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { approveHitl } from "@/lib/api";
import { useIsLightMode } from "@/lib/useTheme";

interface Props {
  runId: string;
  stage: string;
  stageSummary: string;
  onApproved: () => void;
  onDismiss: () => void;
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

export function HitlModal({ runId, stage, stageSummary, onApproved, onDismiss }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const light = useIsLightMode();

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
    <Dialog.Root open onOpenChange={(open) => { if (!open && !loading) onDismiss(); }}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-40"
          style={{ background: "var(--hitl-backdrop)" }}
        />
        <Dialog.Content
          className="ftm-hitl fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50
                     w-[calc(100%-2rem)] max-w-2xl max-h-[calc(100dvh-2rem)] overflow-y-auto
                     rounded-lg p-4 animate-hitl-enter shadow-hitl sm:p-6"
          style={{ background: "var(--hitl-surface)" }}
        >
          <header className="mb-4 flex items-start gap-2 border-b border-hitl/30 pb-3">
            <span className="mt-0.5 text-hitl" aria-hidden>▮▮</span>
            <Dialog.Title asChild>
              <span className="min-w-0 flex-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-content">
                Checkpoint · {copy.title}
              </span>
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={loading}
                aria-label="Close review and return to run"
                className="-m-2 ml-auto flex min-h-11 min-w-11 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-3 hover:text-content disabled:opacity-50"
              >
                <X size={18} aria-hidden />
              </button>
            </Dialog.Close>
          </header>
          <Dialog.Description className="text-content-secondary text-sm mb-4">
            {copy.description}
          </Dialog.Description>

          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
            Draft summary
          </p>
          <div className={`bg-surface-3 rounded-md p-4 max-h-64 overflow-y-auto text-sm mb-5 prose ${light ? "" : "prose-invert"} prose-sm max-w-none text-content-secondary`}>
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

          {error && <p role="alert" className="text-content text-sm mb-3">{error}</p>}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={loading}
                className="min-h-11 rounded-md border border-border-subtle px-5 py-2 text-sm font-medium text-content-secondary transition-colors hover:bg-surface-3 hover:text-content disabled:opacity-50"
              >
                Review later
              </button>
            </Dialog.Close>
            <button
              onClick={handleApprove}
              disabled={loading}
              className="w-full rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-on sm:w-auto sm:py-2
                         hover:bg-primary-hover transition-colors disabled:opacity-50
                         focus:outline-none focus:ring-2 focus:ring-border-focus focus:ring-offset-2
                         focus:ring-offset-surface-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <LoaderCircle size={16} className="animate-spin" aria-hidden />
                  Resuming pipeline…
                </span>
              ) : `${copy.cta} →`}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
