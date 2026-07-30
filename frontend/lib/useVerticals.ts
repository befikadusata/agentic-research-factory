"use client";

import { useState, useEffect } from "react";
import { VERTICALS, type VerticalDefinition, type OutputFormat, type Vertical } from "./types";
import { IS_DEMO } from "./demo";

/**
 * Playbook definitions as the *backend* currently defines them, falling back to
 * the bundled VERTICALS whenever the fetch can't answer.
 *
 * Every surface that labels a run reads this rather than the static constant.
 * They used to disagree — /new asked the backend while the run list and run
 * detail read the bundle — so a playbook added server-side produced runs that
 * could be started but then appeared with no playbook at all.
 */

/** Accent for a playbook the bundle has no palette for. A backend-added vertical
 *  still gets a legible badge instead of an unstyled one. */
const FALLBACK_ACCENT = "text-content-secondary bg-surface-3 border-border-subtle";

// One request per page load, shared by every caller. `useVerticals` now runs
// once per RunCard, so a fetch per mount would mean a request per row in the
// history list.
let cached: VerticalDefinition[] | null = null;
let inFlight: Promise<VerticalDefinition[]> | null = null;

function mapVerticals(data: Record<string, unknown>[]): VerticalDefinition[] {
  return data.map((v) => {
    const key = v.key as Vertical;
    const staticDef = VERTICALS.find((sv) => sv.key === key);
    return {
      key,
      displayName: v.display_name as string,
      description: v.description as string,
      defaultFormat: v.default_format as OutputFormat,
      accentClass: staticDef?.accentClass ?? FALLBACK_ACCENT,
      inputSchema: Object.fromEntries(
        Object.entries(v.input_schema as Record<string, Record<string, unknown>>).map(([k, s]) => [
          k,
          {
            label: s.label as string,
            required: (s.required as boolean) ?? false,
            placeholder: (s.placeholder as string) ?? "",
            type: s.type as "text" | "url" | "select",
            options: s.options as string[] | undefined,
          },
        ])
      ),
    };
  });
}

function loadVerticals(): Promise<VerticalDefinition[]> {
  if (cached) return Promise.resolve(cached);
  if (!inFlight) {
    inFlight = fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/verticals`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: unknown) => (Array.isArray(data) ? mapVerticals(data) : VERTICALS))
      .catch(() => VERTICALS) // the bundled definitions are the fallback
      .then((verticals) => {
        cached = verticals;
        return verticals;
      });
  }
  return inFlight;
}

export function useVerticals(): VerticalDefinition[] {
  const [verticals, setVerticals] = useState<VerticalDefinition[]>(cached ?? VERTICALS);

  useEffect(() => {
    // The static VERTICALS are already the fallback, so demo mode just skips the
    // request rather than logging a connection error for a backend it knows
    // isn't there.
    if (IS_DEMO || cached) return;
    let live = true;
    void loadVerticals().then((v) => {
      if (live) setVerticals(v);
    });
    return () => {
      live = false;
    };
  }, []);

  return verticals;
}

/** The definition for one run's playbook, or null if it has none. */
export function useVertical(key: string | null | undefined): VerticalDefinition | null {
  const verticals = useVerticals();
  return key ? verticals.find((v) => v.key === key) ?? null : null;
}
