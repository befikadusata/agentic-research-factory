import { AGENT_STATE_GLYPH, STATUS_TO_AGENT_STATE, VERTICALS, statusBadgeClass } from "@/lib/types";
import type { Run } from "@/lib/types";
import Link from "next/link";
import { PipelineProgress } from "@/components/PipelineProgress";

export function RunCard({ run }: { run: Run }) {
  const vDef = run.vertical ? VERTICALS.find((v) => v.key === run.vertical) : null;
  const glyph = AGENT_STATE_GLYPH[STATUS_TO_AGENT_STATE[run.status]];

  return (
    <Link
      href={`/runs/${run.id}`}
      className="block bg-surface-2 border border-border-subtle rounded-lg p-5 hover:border-primary transition-all duration-base"
    >
      <div className="flex items-start justify-between gap-4">
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
        <PipelineProgress status={run.status} />
      </div>
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-content-muted text-xs">
            {new Date(run.created_at).toLocaleDateString()}
          </p>
          {vDef && (
            <span className={`text-[10px] font-semibold border px-2 py-0.5 rounded-sm ${vDef.accentClass}`}>
              {vDef.icon} {vDef.displayName}
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
