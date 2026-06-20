"use client";

import { VERTICALS, type VerticalDefinition, type Vertical } from "@/lib/types";
import { clsx } from "clsx";

interface Props {
  value: Vertical | null;
  onChange: (v: Vertical) => void;
}

export function VerticalSelector({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {VERTICALS.map((v: VerticalDefinition) => {
        const selected = value === v.key;
        return (
          <button
            key={v.key}
            type="button"
            onClick={() => onChange(v.key)}
            className={clsx(
              "relative text-left rounded-xl border p-4 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-violet-500",
              selected
                ? "border-violet-500 bg-violet-950/60 shadow-lg shadow-violet-900/30"
                : "border-zinc-700 bg-zinc-900/60 hover:border-zinc-500 hover:bg-zinc-800/60"
            )}
          >
            {selected && (
              <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-violet-400" />
            )}
            <div className="text-2xl mb-2">{v.icon}</div>
            <div
              className={clsx(
                "text-sm font-semibold mb-1",
                selected ? "text-violet-200" : "text-zinc-200"
              )}
            >
              {v.displayName}
            </div>
            <div className="text-xs text-zinc-400 leading-snug">{v.description}</div>
          </button>
        );
      })}
    </div>
  );
}
