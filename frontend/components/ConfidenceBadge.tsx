import type { EvalScores, Vertical } from "@/lib/types";

interface Props {
  scores?: EvalScores;
  /** lead-intel runs have no separate research artifact, so `accuracy` is scored
   *  against the output itself — we flag it rather than present it as grounded. */
  vertical?: Vertical | null;
}

type Band = "high" | "medium" | "low";

function band(score: number): Band {
  if (score >= 80) return "high";
  if (score >= 60) return "medium";
  return "low";
}

const BAND_TEXT: Record<Band, string> = {
  high: "text-feedback-success",
  medium: "text-feedback-warning",
  low: "text-feedback-error",
};

const BAND_METER: Record<Band, string> = {
  high: "bg-feedback-success",
  medium: "bg-feedback-warning",
  low: "bg-feedback-error",
};

const BAND_LABEL: Record<Band, string> = {
  high: "High confidence",
  medium: "Moderate confidence",
  low: "Low confidence",
};

const DIMENSIONS: { key: keyof EvalScores; label: string }[] = [
  { key: "accuracy", label: "Accuracy" },
  { key: "relevance", label: "Relevance" },
  { key: "completeness", label: "Completeness" },
  { key: "writing_quality", label: "Writing" },
];

export function ConfidenceBadge({ scores, vertical }: Props) {
  // eval runs after completion and can fail (LLM judge exception → {}).
  if (!scores || typeof scores.overall !== "number") {
    return (
      <div className="border border-border-subtle rounded-lg bg-surface-2 px-4 py-3">
        <p className="text-sm text-content-muted">
          AI confidence estimate unavailable for this run.
        </p>
      </div>
    );
  }

  const overall = scores.overall;
  const overallBand = band(overall);
  const accuracyUngrounded = vertical === "b2b_sales_lead_intel";

  return (
    <div className="border border-border-subtle rounded-lg bg-surface-2 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-surface-3 border-b border-border-subtle">
        <div className="flex items-baseline gap-2">
          <h2 className="font-semibold text-content">AI Confidence</h2>
          <span
            className="text-xs text-content-muted cursor-help"
            title="LLM-judged quality estimate scored after the run completes. A heuristic signal, not a guarantee."
          >
            ⓘ
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className={`text-2xl font-bold tabular-nums ${BAND_TEXT[overallBand]}`}>
            {Math.round(overall)}
          </span>
          <span className={`text-xs font-semibold uppercase tracking-wider ${BAND_TEXT[overallBand]}`}>
            {BAND_LABEL[overallBand]}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 px-4 py-4">
        {DIMENSIONS.map(({ key, label }) => {
          const value = scores[key];
          if (typeof value !== "number") return null;
          const b = band(value);
          const flagged = key === "accuracy" && accuracyUngrounded;
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-content-secondary font-medium">
                  {label}
                  {flagged && (
                    <span
                      className="ml-1 text-content-muted cursor-help"
                      title="This run type has no separate research artifact, so accuracy is scored against the output itself — treat as indicative only."
                    >
                      *
                    </span>
                  )}
                </span>
                <span className={`text-xs font-semibold tabular-nums ${BAND_TEXT[b]}`}>
                  {Math.round(value)}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
                <div
                  className={`h-full rounded-full ${BAND_METER[b]}`}
                  style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {scores.issues && scores.issues.length > 0 && (
        <div className="px-4 pb-4">
          <div className="rounded-lg border border-feedback-warning/40 bg-feedback-warning/10 px-4 py-3">
            <h3 className="text-xs font-bold text-content-secondary uppercase tracking-wider mb-2">
              Reviewer flagged
            </h3>
            <ul className="list-disc list-inside space-y-1">
              {scores.issues.map((issue, i) => (
                <li key={i} className="text-sm text-content">
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
