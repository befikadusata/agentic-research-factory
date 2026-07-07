"use client";

import { useVerticals } from "@/lib/useVerticals";
import type { VerticalDefinition, Vertical } from "@/lib/types";
import { clsx } from "clsx";

interface Props {
  value: Vertical | null;
  onChange: (v: Vertical) => void;
}

export function VerticalSelector({ value, onChange }: Props) {
  const verticals = useVerticals();
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {verticals.map((v: VerticalDefinition) => {
        const selected = value === v.key;
        return (
          <button
            key={v.key}
            type="button"
            onClick={() => onChange(v.key)}
            className={clsx(
              "relative text-left rounded-lg border p-4 transition-all duration-base ease-standard focus:outline-none focus:ring-2 focus:ring-border-focus",
              selected
                ? "border-agent-active bg-surface-2 shadow-active"
                : "border-border-subtle bg-surface-2 hover:-translate-y-0.5 hover:bg-surface-3"
            )}
          >
            {selected && (
              <span className="absolute top-3 right-3 text-agent-active" aria-hidden>✓</span>
            )}
            <div className="text-2xl mb-2 text-primary">{v.icon}</div>
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
