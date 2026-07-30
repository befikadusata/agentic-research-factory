"use client";

import { AGENT_STATE_GLYPH, STATUS_TO_AGENT_STATE, statusBadgeClass } from "@/lib/types";
import type { Run } from "@/lib/types";
import Link from "next/link";
import { PipelineProgress } from "@/components/PipelineProgress";
import { PlaybookIcon } from "@/components/PlaybookIcon";
import { useVertical } from "@/lib/useVerticals";

export function RunCard({ run }: { run: Run }) {
  const vDef = useVertical(run.vertical);
  const glyph = AGENT_STATE_GLYPH[STATUS_TO_AGENT_STATE[run.status]];

  return (
    <Link
      href={`/runs/${run.id}`}
      className="block bg-surface-2 border border-border-subtle rounded-lg p-4 hover:border-primary transition-all duration-base sm:p-5"
    >
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="font-semibold text-content truncate">{run.topic}</p>
          <p className="text-content-secondary text-sm mt-1 capitalize">{run.format} Run</p>
        </div>
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-sm whitespace-nowrap ${statusBadgeClass(run.status)}`}>
          {glyph && <span aria-hidden>{glyph} </span>}
          {run.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="mt-4">
        <PipelineProgress status={run.status} failedAtStatus={run.failed_at_status} />
      </div>
      <div className="flex flex-col items-start gap-2 mt-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-content-muted text-xs">
            {new Date(run.created_at).toLocaleDateString()}
          </p>
          {vDef && (
            <span className={`inline-flex items-center gap-1 text-[10px] font-semibold border px-2 py-0.5 rounded-sm ${vDef.accentClass}`}>
              <PlaybookIcon vertical={vDef.key} size={12} />
              {vDef.displayName}
            </span>
          )}
        </div>
        {run.status === "failed" && (
          <p className="text-content-secondary text-xs italic">
            Check failed run details
          </p>
        )}
      </div>
    </Link>
  );
}
