import { BarChart3, Compass, FileSearch, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const PLAYBOOK_ICONS: Record<string, LucideIcon> = {
  b2b_sales_lead_intel: Target,
  marketing_competitor_briefs: BarChart3,
  founder_strategy_briefs: Compass,
};

export function PlaybookIcon({
  vertical,
  size = 20,
  className,
}: {
  /** Keyed by string, not the `Vertical` union: the backend is free to define a
   *  playbook this bundle has never heard of. */
  vertical: string;
  size?: number;
  className?: string;
}) {
  // The fallback is required, not cosmetic: an unknown key would resolve to
  // `undefined`, which React rejects as an element type.
  const Icon = PLAYBOOK_ICONS[vertical] ?? FileSearch;
  return <Icon size={size} className={className} strokeWidth={2} aria-hidden />;
}
