"use client";

import type { VerticalDefinition, Vertical } from "@/lib/types";
import { PlaybookIcon } from "@/components/PlaybookIcon";
import { clsx } from "clsx";
import { Check } from "lucide-react";

interface Props {
  value: Vertical | null;
  onChange: (v: Vertical) => void;
  verticals: VerticalDefinition[];
}

export function VerticalSelector({ value, onChange, verticals }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" role="group" aria-label="Playbook">
      {verticals.map((v: VerticalDefinition) => {
        const selected = value === v.key;
        return (
          <button
            key={v.key}
            type="button"
            onClick={() => onChange(v.key)}
            aria-pressed={selected}
            className={clsx(
              "relative text-left rounded-lg border p-4 transition-all duration-base ease-standard focus:outline-none focus:ring-2 focus:ring-border-focus",
              selected
                ? "border-agent-active bg-surface-2 shadow-active"
                : "border-border-subtle bg-surface-2 hover:-translate-y-0.5 hover:bg-surface-3"
            )}
          >
            {selected && (
              <span className="absolute right-3 top-3 text-agent-active" aria-hidden>
                <Check size={18} strokeWidth={2.5} />
              </span>
            )}
            <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
              <PlaybookIcon vertical={v.key} size={22} />
            </div>
            <div
              className={clsx(
                "text-sm font-semibold mb-1",
                selected ? "text-content" : "text-content-secondary"
              )}
            >
              {v.displayName}
            </div>
            <div className="text-xs text-content-muted leading-snug">{v.description}</div>
          </button>
        );
      })}
    </div>
  );
}
