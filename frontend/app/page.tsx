"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getRuns } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { RunCard } from "@/components/RunCard";
import type { Run } from "@/lib/types";

export default function Dashboard() {
  const { status } = useSession();
  const { activeId, active } = useWorkspace();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !activeId) return;
    setLoading(true);
    setError(null);
    getRuns(activeId)
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status, activeId]);

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-content">Recent Runs</h1>
          {active && <p className="text-sm text-content-muted mt-1">{active.name}</p>}
        </div>
        <a
          href="/new"
          className="bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base flex items-center gap-2"
        >
          Create New Run
        </a>
      </div>

      {loading && <p className="text-content-muted">Loading runs…</p>}
      {error && <p className="text-content bg-feedback-error/10 border border-feedback-error/40 p-4 rounded-lg">{error}</p>}
      {!loading && !error && runs.length === 0 && (
        <div className="border-2 border-dashed border-border-subtle rounded-lg p-16 text-center text-content-muted">
          <p className="text-lg mb-4">No research runs yet.</p>
          <a href="/new" className="text-primary hover:text-primary-hover font-medium">Create your first research run →</a>
        </div>
      )}

      <div className="space-y-4">
        {runs.map((run) => (
          <RunCard key={run.id} run={run} />
        ))}
      </div>
    </div>
  );
}
