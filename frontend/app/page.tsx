"use client";

import { useEffect, useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { getRuns } from "@/lib/api";
import { RunCard } from "@/components/RunCard";
import type { Run } from "@/lib/types";

export default function Dashboard() {
  const { data: session, status } = useSession();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated") return;
    getRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status]);

  if (status === "loading") return <p className="text-content-muted p-8">Loading…</p>;

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <h1 className="text-4xl font-bold mb-4 text-content">Research Factory</h1>
        <p className="text-content-secondary mb-8 max-w-md">Autonomous research powered by intelligent agents. Sign in to get started.</p>
        <button
          onClick={() => signIn("google")}
          className="bg-primary hover:bg-primary-hover text-primary-on font-medium px-8 py-3 rounded-md transition-colors duration-base"
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-content">Recent Runs</h1>
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
