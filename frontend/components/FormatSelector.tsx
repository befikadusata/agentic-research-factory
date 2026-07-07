"use client";

import type { OutputFormat } from "@/lib/types";

const OPTIONS: { value: OutputFormat; label: string; desc: string }[] = [
  { value: "report",   label: "Full Report",        desc: "1,500–2,500 word research report with citations" },
  { value: "linkedin", label: "LinkedIn Article",   desc: "1,200–1,500 word professional article" },
  { value: "summary",  label: "Executive Summary",  desc: "400–600 word one-pager for decision makers" },
];

interface Props {
  value: OutputFormat;
  onChange: (v: OutputFormat) => void;
}

export function FormatSelector({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`text-left p-4 rounded-lg border transition-colors duration-base
            ${value === opt.value
              ? "border-agent-active bg-surface-2 shadow-active"
              : "border-border-subtle bg-surface-2 hover:border-border-strong"}`}
        >
          <p className="font-medium text-sm text-content">{opt.label}</p>
          <p className="text-content-muted text-xs mt-1">{opt.desc}</p>
        </button>
      ))}
    </div>
  );
}
