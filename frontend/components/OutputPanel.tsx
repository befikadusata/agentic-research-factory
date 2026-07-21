"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadOutput } from "@/lib/api";
import { DownloadButton } from "./DownloadButton";
import { useIsLightMode } from "@/lib/useTheme";

interface Props {
  content: string;
  runId: string;
}

export function OutputPanel({ content, runId }: Props) {
  const [downloading, setDownloading] = useState<"pdf" | "md" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const light = useIsLightMode();

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
    <div className="border border-border-subtle rounded-lg overflow-hidden bg-surface-2">
      <div className="flex flex-col items-start gap-3 px-4 py-3 bg-surface-3 border-b border-border-subtle sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-semibold text-content">Output</h2>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
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
        <p role="alert" className="text-content text-sm px-4 py-2 bg-feedback-error/10 border-b border-feedback-error/30">
          {downloadError}
        </p>
      )}
      <div className={`p-4 prose ${light ? "" : "prose-invert"} max-w-none overflow-y-auto max-h-[60vh] break-words sm:p-6`}>
        {content?.trim() ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        ) : (
          <p className="text-content-muted italic not-prose">Output content is unavailable.</p>
        )}
      </div>
    </div>
  );
}
