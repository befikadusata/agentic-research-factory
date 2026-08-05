import { Clock, Coins } from "lucide-react";
import type { RunCost } from "@/lib/types";
import { formatDuration, formatTokens, formatUsd } from "@/lib/format";

/**
 * What a single run actually consumed: tokens and dollars per agent, plus
 * wall-clock time.
 *
 * Rendered for failed runs too — a run that died mid-pipeline still burned
 * tokens, and hiding that is how a bill becomes a surprise.
 */
export function RunCostPanel({
  costs,
  latencySec,
}: {
  costs?: RunCost[];
  latencySec?: number;
}) {
  if (!costs || costs.length === 0) return null;

  // One row per call, so an agent that ran twice appears twice. Fold them.
  const byAgent = new Map<string, { input: number; output: number; cost: number; calls: number }>();
  for (const c of costs) {
    const agent = byAgent.get(c.agent_name) ?? { input: 0, output: 0, cost: 0, calls: 0 };
    agent.input += c.input_tokens;
    agent.output += c.output_tokens;
    agent.cost += c.total_cost;
    agent.calls += 1;
    byAgent.set(c.agent_name, agent);
  }
  const rows = [...byAgent.entries()].sort((a, b) => b[1].cost - a[1].cost || b[1].input - a[1].input);

  const totalInput = costs.reduce((sum, c) => sum + c.input_tokens, 0);
  const totalOutput = costs.reduce((sum, c) => sum + c.output_tokens, 0);
  const totalCost = costs.reduce((sum, c) => sum + c.total_cost, 0);

  // A pipeline routed entirely to free-tier models really does cost $0, which
  // needs saying: "$0.00" beside six figures of tokens reads as a broken meter.
  const freeTier = totalCost === 0 && totalInput + totalOutput > 0;

  return (
    <div className="border border-border-subtle rounded-lg overflow-hidden bg-surface-2">
      <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-border-subtle bg-surface-3">
        <Coins size={16} className="text-content-muted" aria-hidden />
        <h2 className="font-semibold text-content">Cost &amp; usage</h2>
        {latencySec !== undefined && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-sm text-content-secondary">
            <Clock size={14} aria-hidden />
            {formatDuration(latencySec)}
          </span>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-px bg-border-subtle sm:grid-cols-3">
        <div className="bg-surface-2 px-4 py-3">
          <dt className="text-xs font-medium text-content-muted">Input tokens</dt>
          <dd className="mt-0.5 text-lg font-semibold text-content tabular-nums">{formatTokens(totalInput)}</dd>
        </div>
        <div className="bg-surface-2 px-4 py-3">
          <dt className="text-xs font-medium text-content-muted">Output tokens</dt>
          <dd className="mt-0.5 text-lg font-semibold text-content tabular-nums">{formatTokens(totalOutput)}</dd>
        </div>
        <div className="bg-surface-2 px-4 py-3 col-span-2 sm:col-span-1">
          <dt className="text-xs font-medium text-content-muted">Total cost</dt>
          <dd className="mt-0.5 text-lg font-semibold text-content tabular-nums">
            {freeTier ? "Free tier" : formatUsd(totalCost)}
          </dd>
        </div>
      </dl>

      {freeTier && (
        <p className="px-4 py-3 text-sm text-content-secondary border-t border-border-subtle">
          Every model this run used is priced at zero, so the tokens above are real but the
          spend is not. Point an agent at a paid model and this becomes a dollar figure.
        </p>
      )}

      <table className="w-full border-t border-border-subtle text-sm">
        <caption className="sr-only">Token usage and cost per agent</caption>
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-content-muted">
            <th scope="col" className="px-4 py-2 font-semibold">Agent</th>
            <th scope="col" className="px-4 py-2 font-semibold text-right">In</th>
            <th scope="col" className="px-4 py-2 font-semibold text-right">Out</th>
            <th scope="col" className="px-4 py-2 font-semibold text-right">Cost</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {rows.map(([agent, totals]) => (
            <tr key={agent}>
              <th scope="row" className="px-4 py-2 text-left font-medium text-content break-words">
                {agent}
                {totals.calls > 1 && (
                  <span className="ml-1.5 text-xs font-normal text-content-muted">
                    ×{totals.calls}
                  </span>
                )}
              </th>
              <td className="px-4 py-2 text-right text-content-secondary tabular-nums">{formatTokens(totals.input)}</td>
              <td className="px-4 py-2 text-right text-content-secondary tabular-nums">{formatTokens(totals.output)}</td>
              <td className="px-4 py-2 text-right text-content-secondary tabular-nums">{formatUsd(totals.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
