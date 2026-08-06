import Link from "next/link";
import { Radar } from "lucide-react";
import type { Monitor } from "@/lib/types";
import { formatInterval, formatRelative } from "@/lib/monitors";
import { PlaybookIcon } from "@/components/PlaybookIcon";
import { useVertical } from "@/lib/useVerticals";

export function MonitorCard({ monitor }: { monitor: Monitor }) {
  const vDef = useVertical(monitor.vertical);

  return (
    <Link
      href={`/monitors/${monitor.id}`}
      className="block bg-surface-2 border border-border-subtle rounded-lg p-4 hover:border-primary transition-all duration-base sm:p-5"
    >
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="font-semibold text-content truncate flex items-center gap-2">
            <Radar size={16} className="text-content-muted shrink-0" />
            {monitor.name}
          </p>
          <p className="text-content-secondary text-sm mt-1 truncate">{monitor.topic}</p>
        </div>
        <span
          className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-sm whitespace-nowrap ${
            monitor.enabled
              ? "text-feedback-success bg-feedback-success/10"
              : "text-content-muted bg-surface-3"
          }`}
        >
          {monitor.enabled ? "Active" : "Paused"}
        </span>
      </div>
      <div className="flex items-center gap-3 mt-4 text-xs text-content-muted flex-wrap">
        {vDef && (
          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold border px-2 py-0.5 rounded-sm ${vDef.accentClass}`}>
            <PlaybookIcon vertical={vDef.key} size={12} />
            {vDef.displayName}
          </span>
        )}
        <span>{formatInterval(monitor.interval_minutes)}</span>
        <span aria-hidden>·</span>
        <span>
          {monitor.enabled ? `Next run ${formatRelative(monitor.next_run_at)}` : "Paused"}
        </span>
        {monitor.last_run_at && (
          <>
            <span aria-hidden>·</span>
            <span>Last run {formatRelative(monitor.last_run_at)}</span>
          </>
        )}
      </div>
    </Link>
  );
}
