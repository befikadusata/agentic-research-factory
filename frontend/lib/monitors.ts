export const INTERVAL_PRESETS: { label: string; minutes: number }[] = [
  { label: "Every hour", minutes: 60 },
  { label: "Every 6 hours", minutes: 360 },
  { label: "Daily", minutes: 1440 },
  { label: "Weekly", minutes: 10080 },
];

export function formatInterval(minutes: number): string {
  const preset = INTERVAL_PRESETS.find((p) => p.minutes === minutes);
  if (preset) return preset.label;
  if (minutes % 1440 === 0) return `Every ${minutes / 1440} days`;
  if (minutes % 60 === 0) return `Every ${minutes / 60} hours`;
  return `Every ${minutes} min`;
}

export function formatRelative(iso?: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diffMs = then - Date.now();
  const past = diffMs < 0;
  const mins = Math.round(Math.abs(diffMs) / 60000);
  const rel =
    mins < 1 ? "just now"
    : mins < 60 ? `${mins} min`
    : mins < 1440 ? `${Math.round(mins / 60)} hr`
    : `${Math.round(mins / 1440)} d`;
  if (rel === "just now") return rel;
  return past ? `${rel} ago` : `in ${rel}`;
}
