import Link from "next/link";
import { Radar } from "lucide-react";
import type { Monitor } from "@/lib/types";
import { formatInterval, formatRelative } from "@/lib/monitors";

export function MonitorCard({ monitor }: { monitor: Monitor }) {
  return (
    <Link
      href={`/monitors/${monitor.id}`}
      className="block bg-surface-2 border border-border-subtle rounded-lg p-5 hover:border-primary transition-all duration-base"
    >
      <div className="flex items-start justify-between gap-4">
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
