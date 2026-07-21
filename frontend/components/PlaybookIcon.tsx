import { BarChart3, Compass, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Vertical } from "@/lib/types";

const PLAYBOOK_ICONS: Record<Vertical, LucideIcon> = {
  b2b_sales_lead_intel: Target,
  marketing_competitor_briefs: BarChart3,
  founder_strategy_briefs: Compass,
};

export function PlaybookIcon({
  vertical,
  size = 20,
  className,
}: {
  vertical: Vertical;
  size?: number;
  className?: string;
}) {
  const Icon = PLAYBOOK_ICONS[vertical];
  return <Icon size={size} className={className} strokeWidth={2} aria-hidden />;
}
