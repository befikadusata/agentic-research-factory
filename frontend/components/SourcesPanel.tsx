import { ExternalLink, FileText, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Citation } from "@/lib/types";

/** The sources a report cites, marked with whether the run actually retrieved them.
 *
 *  Agents fabricate citations that look entirely ordinary — one live run cited
 *  six well-known consultancies and universities, none of which it had visited.
 *  The backend checks each URL against the sources it really fetched; this is
 *  where that shows up, because a warning buried in the logs protects nobody
 *  reading the report. */
export function SourcesPanel({ citations }: { citations?: Citation[] }) {
  if (!citations || citations.length === 0) return null;

  const unverified = citations.filter((c) => c.verified === false).length;
  // Full literal class strings — Tailwind can't compile interpolated names.
  const style = unverified
    ? { border: "border-feedback-warning/40", head: "border-feedback-warning/30 bg-feedback-warning/10", icon: "text-feedback-warning" }
    : { border: "border-border-subtle", head: "border-border-subtle bg-surface-3", icon: "text-content-muted" };

  return (
    <div className={`border rounded-lg overflow-hidden bg-surface-2 ${style.border}`}>
      <div className={`flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b ${style.head}`}>
        <div className="flex items-center gap-2">
          {unverified ? (
            <ShieldAlert size={16} className={style.icon} aria-hidden />
          ) : (
            <ShieldCheck size={16} className={style.icon} aria-hidden />
          )}
          <h2 className="font-semibold text-content">Sources</h2>
          <span className="text-xs text-content-muted tabular-nums">({citations.length})</span>
        </div>
        {unverified > 0 && (
          <p className="text-sm font-semibold text-content">
            {unverified} of {citations.length} could not be verified
          </p>
        )}
      </div>

      {unverified > 0 && (
        <p className="px-4 py-3 text-sm text-content-secondary border-b border-border-subtle">
          Flagged sources are ones this run has no record of retrieving. Some may still be
          genuine — a link quoted inside another page, for instance — but others are invented
          by the writing agent. Check them before relying on the claims they support.
        </p>
      )}

      <ul className="divide-y divide-border-subtle">
        {citations.map((c, i) => {
          const isWeb = /^https?:\/\//i.test(c.page);
          const flagged = c.verified === false;
          return (
            <li key={`${c.source}-${c.page}-${i}`} className="px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-content break-words">{c.source}</p>
                  {isWeb ? (
                    <a
                      href={c.page}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-0.5 inline-flex items-start gap-1 text-xs text-content-muted underline break-all hover:text-content"
                    >
                      {c.page}
                      <ExternalLink size={11} className="mt-0.5 flex-none" aria-hidden />
                    </a>
                  ) : (
                    <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-content-muted">
                      <FileText size={11} className="flex-none" aria-hidden />
                      Page {c.page}
                    </p>
                  )}
                </div>
                {flagged ? (
                  <span
                    className="inline-flex flex-none items-center gap-1 rounded-sm border border-feedback-warning/40 bg-feedback-warning/10 px-2 py-0.5 text-xs font-semibold text-content"
                    title="The run has no record of fetching this URL — it may have been invented by the agent."
                  >
                    <ShieldAlert size={12} className="text-feedback-warning" aria-hidden />
                    Unverified
                  </span>
                ) : c.verified === true ? (
                  <span
                    className="inline-flex flex-none items-center gap-1 rounded-sm border border-feedback-success/40 bg-feedback-success/10 px-2 py-0.5 text-xs font-semibold text-content"
                    title="This run retrieved this URL during research."
                  >
                    <ShieldCheck size={12} className="text-feedback-success" aria-hidden />
                    Retrieved
                  </span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
