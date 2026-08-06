"use client";

import { useState, useEffect } from "react";
import { VERTICALS, type VerticalDefinition, type OutputFormat, type Vertical } from "./types";
import { IS_DEMO } from "./demo";

/**
 * The single source of playbook definitions for every surface that labels a
 * run: the backend's list, falling back to the bundled VERTICALS.
 */

/** Accent for a playbook the bundle has no palette for, so a backend-added
 *  vertical still gets a legible badge. */
const FALLBACK_ACCENT = "text-content-secondary bg-surface-3 border-border-subtle";

// One request per page load, shared by every caller: `useVerticals` runs once
// per RunCard, so fetching per mount would mean a request per history row.
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
      .catch(() => VERTICALS)
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
    // Demo mode skips the request rather than logging a connection error for a
    // backend it knows isn't there; the static VERTICALS already stand in.
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

export function useVertical(key: string | null | undefined): VerticalDefinition | null {
  const verticals = useVerticals();
  return key ? verticals.find((v) => v.key === key) ?? null : null;
}
