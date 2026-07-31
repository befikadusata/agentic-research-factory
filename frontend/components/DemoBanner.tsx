import { FlaskConical } from "lucide-react";
import { IS_DEMO } from "@/lib/demo";

/**
 * Persistent "this is not real data" marker for demo builds.
 *
 * It stays for the whole session rather than being dismissible on purpose: the
 * demo is meant to be screenshotted and linked, and a banner that can be closed
 * is a banner that will be missing from the screenshot.
 *
 * Renders nothing outside demo mode, so it costs a production build nothing.
 */
export function DemoBanner() {
  if (!IS_DEMO) return null;

  return (
    <div
      role="note"
      className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-hitl/40 bg-hitl/10 px-4 py-2 text-center text-xs text-content"
    >
      <FlaskConical size={14} className="shrink-0 text-hitl" aria-hidden />
      <span className="font-semibold">Demo mode</span>
      <span className="text-content-secondary">
        Sample data, scripted agent runs, no backend. Nothing here is saved.
      </span>
    </div>
  );
}
