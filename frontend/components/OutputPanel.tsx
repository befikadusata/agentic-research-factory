"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
  pdfUrl: string;
  mdUrl: string;
}

export function OutputPanel({ content, pdfUrl, mdUrl }: Props) {
  return (
    <div className="border border-zinc-700 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-zinc-800 border-b border-zinc-700">
        <h2 className="font-semibold">Output</h2>
        <div className="flex gap-2">
          <a
            href={pdfUrl}
            target="_blank"
            rel="noreferrer"
            className="text-sm bg-violet-600 hover:bg-violet-700 text-white px-3 py-1.5 rounded-lg"
          >
            Download PDF
          </a>
          <a
            href={mdUrl}
            target="_blank"
            rel="noreferrer"
            className="text-sm border border-zinc-600 px-3 py-1.5 rounded-lg hover:bg-zinc-700"
          >
            Download MD
          </a>
        </div>
      </div>
      <div className="p-6 prose prose-invert max-w-none overflow-y-auto max-h-[60vh]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
