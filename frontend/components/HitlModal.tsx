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
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl bg-zinc-900 rounded-xl shadow-2xl p-6 border border-zinc-700">
          <Dialog.Title className="text-xl font-bold mb-1">
            ⏸ {copy.title}
          </Dialog.Title>
          <Dialog.Description className="text-zinc-400 text-sm mb-4">
            {copy.description}
          </Dialog.Description>

          <div className="bg-zinc-800 rounded-lg p-4 max-h-64 overflow-y-auto text-sm mb-4 prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{stageSummary}</ReactMarkdown>
          </div>

          <label className="block text-sm font-medium mb-1 text-zinc-300">
            {copy.feedbackLabel}
          </label>
          <div className="flex flex-wrap gap-2 mb-2">
            {PROMPT_TEMPLATES.map((t) => (
              <button
                key={t}
                onClick={() => setInstruction((prev) => prev ? `${prev}\n${t}` : t)}
                className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-400 px-2 py-1 rounded border border-zinc-700"
              >
                {t}
              </button>
            ))}
          </div>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g. Focus more on pricing strategy and enterprise segment"
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-sm resize-none h-20 mb-4 text-zinc-100 placeholder-zinc-500"
          />

          {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

          <div className="flex justify-end">
            <button
              onClick={handleApprove}
              disabled={loading}
              className="bg-violet-600 hover:bg-violet-700 text-white font-medium px-6 py-2 rounded-lg disabled:opacity-50"
            >
              {loading ? "Resuming…" : copy.cta}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
