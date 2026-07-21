"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { getRuns } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { RunCard } from "@/components/RunCard";
import { CardListSkeleton, LoadError } from "@/components/ListState";
import type { Run } from "@/lib/types";

export default function Dashboard() {
  const { status } = useSession();
  const { activeId, active } = useWorkspace();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(() => {
    if (status !== "authenticated" || !activeId) return;
    setLoading(true);
    setError(null);
    getRuns(activeId)
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status, activeId]);

  useEffect(loadRuns, [loadRuns]);

  return (
    <div className="max-w-4xl">
      <div className="flex flex-col items-start gap-4 mb-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-content">Recent Runs</h1>
          {active && <p className="text-sm text-content-muted mt-1">{active.name}</p>}
        </div>
        <Link
          href="/new"
          className="min-h-11 bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium px-5 py-2.5 rounded-md transition-colors duration-base flex items-center gap-2"
        >
          <Plus size={16} aria-hidden /> Create New Run
        </Link>
      </div>

      {loading && <CardListSkeleton label="Loading research runs" />}
      {!loading && error && (
        <LoadError title="Runs couldn’t be loaded" message={error} onRetry={loadRuns} />
      )}
      {!loading && !error && runs.length === 0 && (
        <div className="border-2 border-dashed border-border-subtle rounded-lg px-6 py-12 text-center text-content-muted sm:p-16">
          <p className="text-lg mb-4">No research runs yet.</p>
          <Link href="/new" className="inline-flex min-h-11 items-center text-primary hover:text-primary-hover font-medium">
            Create your first research run →
          </Link>
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
