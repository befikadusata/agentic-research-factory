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

  async function handleDownload(format: "pdf" | "md") {
    setDownloading(format);
    try {
      await downloadOutput(runId, format);
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
      <div className="p-6 prose prose-invert max-w-none overflow-y-auto max-h-[60vh]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
