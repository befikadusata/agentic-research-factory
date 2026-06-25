"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadOutput } from "@/lib/api";
import { DownloadButton } from "./DownloadButton";

interface Props {
  content: string;
  runId: string;
}

export function OutputPanel({ content, runId }: Props) {
  const [downloading, setDownloading] = useState<"pdf" | "md" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function handleDownload(format: "pdf" | "md") {
    setDownloading(format);
    setDownloadError(null);
    try {
      await downloadOutput(runId, format);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : "Download failed. Please try again.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="border border-zinc-700 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-zinc-800 border-b border-zinc-700">
        <h2 className="font-semibold">Output</h2>
        <div className="flex gap-2">
          <DownloadButton
            label={downloading === "pdf" ? "Downloading…" : "Download PDF"}
            variant="primary"
            disabled={downloading !== null}
            onClick={() => handleDownload("pdf")}
          />
          <DownloadButton
            label={downloading === "md" ? "Downloading…" : "Download MD"}
            disabled={downloading !== null}
            onClick={() => handleDownload("md")}
          />
        </div>
      </div>
      {downloadError && (
        <p className="text-red-400 text-sm px-4 py-2 bg-red-950/20 border-b border-red-900/30">
          {downloadError}
        </p>
      )}
      <div className="p-6 prose prose-invert max-w-none overflow-y-auto max-h-[60vh]">
        {content?.trim() ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        ) : (
          <p className="text-zinc-500 italic not-prose">Output content is unavailable.</p>
        )}
      </div>
    </div>
  );
}
