"use client";

import { useState, useEffect } from "react";
import { VERTICALS, type VerticalDefinition, type OutputFormat, type Vertical } from "./types";

export function useVerticals(): VerticalDefinition[] {
  const [verticals, setVerticals] = useState<VerticalDefinition[]>(VERTICALS);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/verticals`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: unknown) => {
        if (!Array.isArray(data)) return;
        const mapped: VerticalDefinition[] = (data as Record<string, unknown>[]).map((v) => {
          const staticDef = VERTICALS.find((sv) => sv.key === (v.key as Vertical));
          return {
            key: v.key as Vertical,
            displayName: v.display_name as string,
            description: v.description as string,
            icon: v.icon as string,
            defaultFormat: v.default_format as OutputFormat,
            accentClass: staticDef?.accentClass ?? "",
            inputSchema: Object.fromEntries(
              Object.entries(v.input_schema as Record<string, Record<string, unknown>>).map(
                ([k, s]) => [
                  k,
                  {
                    label: s.label as string,
                    required: (s.required as boolean) ?? false,
                    placeholder: (s.placeholder as string) ?? "",
                    type: s.type as "text" | "url" | "select",
                    options: s.options as string[] | undefined,
                  },
                ]
              )
            ),
          };
        });
        setVerticals(mapped);
      })
      .catch(() => {}); // silently fall back to static VERTICALS on any error
  }, []);

  return verticals;
}
