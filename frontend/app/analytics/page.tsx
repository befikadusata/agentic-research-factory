"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Coins, Gauge } from "lucide-react";
import { getAnalyticsCosts, getAnalyticsMetrics } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { LoadError } from "@/components/ListState";
import { formatDuration, formatTokens, formatUsd } from "@/lib/format";
import type { AnalyticsCosts, AnalyticsMetrics } from "@/lib/types";

/** Quality dimensions in the order the eval judge reports them, `overall` first
 *  because it is the one people actually read. */
const SCORE_FIELDS: { key: keyof AnalyticsMetrics["averages"]; label: string }[] = [
  { key: "overall", label: "Overall" },
  { key: "accuracy", label: "Accuracy" },
  { key: "relevance", label: "Relevance" },
  { key: "completeness", label: "Completeness" },
  { key: "writing_quality", label: "Writing quality" },
];

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-2 px-4 py-4">
      <dt className="text-xs font-medium uppercase tracking-wider text-content-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-bold text-content tabular-nums">{value}</dd>
      {hint && <p className="mt-1 text-xs text-content-muted">{hint}</p>}
    </div>
  );
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-content-secondary">{label}</span>
        <span className="text-sm font-semibold text-content tabular-nums">{Math.round(score)}</span>
      </div>
      <div
        role="meter"
        aria-valuenow={Math.round(score)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Average ${label.toLowerCase()} score`}
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-3"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { status } = useSession();
  const { activeId, active } = useWorkspace();
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null);
  const [costs, setCosts] = useState<AnalyticsCosts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (status !== "authenticated" || !activeId) return;
    setLoading(true);
    setError(null);
    Promise.all([getAnalyticsMetrics(activeId), getAnalyticsCosts(activeId)])
      .then(([m, c]) => {
        setMetrics(m);
        setCosts(c);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Analytics could not be loaded."))
      .finally(() => setLoading(false));
  }, [status, activeId]);

  useEffect(load, [load]);

  const totalTokens = costs ? costs.total_input_tokens + costs.total_output_tokens : 0;
  // Same reasoning as the per-run panel: a free-tier pipeline genuinely costs
  // nothing, and "$0.00" beside millions of tokens looks like a broken meter.
  const freeTier = costs !== null && costs.total_cost_usd === 0 && totalTokens > 0;
  const scores = SCORE_FIELDS.map((f) => ({ ...f, value: metrics?.averages[f.key] })).filter(
    (f): f is typeof f & { value: number } => typeof f.value === "number" && f.value > 0,
  );

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-content">Analytics</h1>
        {active && <p className="mt-1 text-sm text-content-muted">{active.name}</p>}
      </div>

      {loading && (
        <div role="status" aria-label="Loading analytics" className="space-y-6 animate-pulse">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} aria-hidden className="h-24 rounded-lg bg-surface-2" />
            ))}
          </div>
          <div aria-hidden className="h-56 rounded-lg bg-surface-2" />
          <span className="sr-only">Loading analytics…</span>
        </div>
      )}

      {!loading && error && (
        <LoadError title="Analytics couldn’t be loaded" message={error} onRetry={load} />
      )}

      {!loading && !error && metrics && costs && (
        <div className="space-y-10">
          <section aria-labelledby="quality-heading">
            <h2 id="quality-heading" className="mb-4 flex items-center gap-2 text-lg font-semibold text-content">
              <Gauge size={18} className="text-content-muted" aria-hidden />
              Quality &amp; speed
            </h2>

            {metrics.count === 0 ? (
              <p className="rounded-lg border border-dashed border-border-subtle px-4 py-8 text-center text-sm text-content-muted">
                No completed runs in this workspace yet. Scores and timings appear once a run finishes.
              </p>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Stat label="Completed runs" value={String(metrics.count)} />
                  <Stat
                    label="Avg. duration"
                    value={formatDuration(metrics.averages.latency_sec ?? 0)}
                    hint="Start to final output"
                  />
                  <Stat
                    label="Avg. sources"
                    value={(metrics.averages.citations ?? 0).toFixed(1)}
                    hint="Citations per report"
                  />
                </dl>

                {scores.length > 0 && (
                  <div className="mt-6 space-y-4 rounded-lg border border-border-subtle bg-surface-2 px-4 py-5">
                    {scores.map((s) => (
                      <ScoreBar key={s.key} label={s.label} score={s.value} />
                    ))}
                    <p className="pt-1 text-xs text-content-muted">
                      Averaged across completed runs, scored 0–100 by the evaluation model. These are
                      one model&apos;s judgement of another&apos;s output, not ground truth — useful for
                      spotting drift between runs, not for certifying a single one.
                    </p>
                  </div>
                )}
              </>
            )}
          </section>

          <section aria-labelledby="cost-heading">
            <h2 id="cost-heading" className="mb-4 flex items-center gap-2 text-lg font-semibold text-content">
              <Coins size={18} className="text-content-muted" aria-hidden />
              Cost &amp; usage
            </h2>

            {totalTokens === 0 ? (
              <p className="rounded-lg border border-dashed border-border-subtle px-4 py-8 text-center text-sm text-content-muted">
                No recorded model usage in this workspace yet.
              </p>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Stat label="Input tokens" value={formatTokens(costs.total_input_tokens)} />
                  <Stat label="Output tokens" value={formatTokens(costs.total_output_tokens)} />
                  <Stat
                    label="Total spend"
                    value={freeTier ? "Free tier" : formatUsd(costs.total_cost_usd)}
                    hint="Every run, including failed ones"
                  />
                </dl>

                {freeTier && (
                  <p className="mt-4 text-sm text-content-secondary">
                    Every model these runs used is priced at zero. The token counts are real; the
                    spend only becomes a dollar figure once an agent is pointed at a paid model.
                  </p>
                )}

                {costs.per_agent.length > 0 && (
                  <div className="mt-6 overflow-x-auto rounded-lg border border-border-subtle bg-surface-2">
                    <table className="w-full min-w-[28rem] text-sm">
                      <caption className="sr-only">Token usage and cost per agent across all runs</caption>
                      <thead>
                        <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wider text-content-muted">
                          <th scope="col" className="px-4 py-2 font-semibold">Agent</th>
                          <th scope="col" className="px-4 py-2 text-right font-semibold">In</th>
                          <th scope="col" className="px-4 py-2 text-right font-semibold">Out</th>
                          <th scope="col" className="px-4 py-2 text-right font-semibold">Cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border-subtle">
                        {[...costs.per_agent]
                          .sort((a, b) => b.cost - a.cost || b.input_tokens - a.input_tokens)
                          .map((a) => (
                            <tr key={a.agent_name}>
                              <th scope="row" className="px-4 py-2 text-left font-medium text-content break-words">
                                {a.agent_name}
                              </th>
                              <td className="px-4 py-2 text-right tabular-nums text-content-secondary">
                                {formatTokens(a.input_tokens)}
                              </td>
                              <td className="px-4 py-2 text-right tabular-nums text-content-secondary">
                                {formatTokens(a.output_tokens)}
                              </td>
                              <td className="px-4 py-2 text-right tabular-nums text-content-secondary">
                                {formatUsd(a.cost)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
