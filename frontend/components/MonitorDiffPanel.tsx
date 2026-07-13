import { GitCompare } from "lucide-react";
import type { MonitorDiff } from "@/lib/types";

export function MonitorDiffPanel({ diff }: { diff?: MonitorDiff }) {
  if (!diff) return null;

  if (diff.baseline) {
    return (
      <div className="border border-border-subtle rounded-lg bg-surface-2 px-4 py-3 flex items-center gap-2">
        <GitCompare size={16} className="text-content-muted shrink-0" />
        <p className="text-sm text-content-muted">
          Baseline run — later runs of this monitor are compared against it.
        </p>
      </div>
    );
  }

  const changed = diff.changed;
  // Full literal class strings — Tailwind can't compile interpolated names.
  const style = changed
    ? { border: "border-feedback-warning/40", head: "border-feedback-warning/30 bg-feedback-warning/10", icon: "text-feedback-warning" }
    : { border: "border-feedback-success/40", head: "border-feedback-success/30 bg-feedback-success/10", icon: "text-feedback-success" };

  return (
    <div className={`border rounded-lg overflow-hidden bg-surface-2 ${style.border}`}>
      <div className={`flex items-center gap-2 px-4 py-3 border-b ${style.head}`}>
        <GitCompare size={16} className={style.icon} />
        <h2 className="font-semibold text-content">
          {changed ? "Changes since last run" : "No material changes"}
        </h2>
      </div>
      <div className="px-4 py-4">
        <p className="text-sm text-content">{diff.summary}</p>
        {diff.highlights && diff.highlights.length > 0 && (
          <ul className="list-disc list-inside space-y-1 mt-3">
            {diff.highlights.map((h, i) => (
              <li key={i} className="text-sm text-content-secondary">{h}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
