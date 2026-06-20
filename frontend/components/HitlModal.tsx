"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { approveHitl } from "@/lib/api";

interface Props {
  runId: string;
  researchSummary: string;
  onApproved: () => void;
}

export function HitlModal({ runId, researchSummary, onApproved }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
            ⏸ Research Complete — Review Before Writing
          </Dialog.Title>
          <Dialog.Description className="text-zinc-400 text-sm mb-4">
            Review the summary below, optionally redirect the focus, then approve to continue.
          </Dialog.Description>

          <div className="bg-zinc-800 rounded-lg p-4 max-h-64 overflow-y-auto text-sm mb-4 prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{researchSummary}</ReactMarkdown>
          </div>

          <label className="block text-sm font-medium mb-1 text-zinc-300">
            Optional: redirect the focus for the writing phase
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
              {loading ? "Resuming…" : "Approve & Continue Writing"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
