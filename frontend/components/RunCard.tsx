import { STATUS_COLORS } from "@/lib/types";
import type { Run } from "@/lib/types";
import Link from "next/link";

export function RunCard({ run }: { run: Run }) {
  return (
    <Link
      href={`/runs/${run.id}`}
      className="block bg-zinc-900 border border-zinc-800 rounded-lg p-5 hover:border-primary-500 transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-semibold text-zinc-100 truncate">{run.topic}</p>
          <p className="text-zinc-400 text-sm mt-1 capitalize">{run.format} Run</p>
        </div>
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-sm whitespace-nowrap ${STATUS_COLORS[run.status] ?? "bg-zinc-800 text-zinc-300"}`}>
          {run.status.replace("_", " ")}
        </span>
      </div>
      <div className="flex items-center justify-between mt-4">
        <p className="text-zinc-500 text-xs">
          {new Date(run.created_at).toLocaleDateString()}
        </p>
        {run.status === "failed" && (
          <p className="text-red-400 text-xs italic">
            Check failed run details
          </p>
        )}
      </div>
    </Link>
  );
}
