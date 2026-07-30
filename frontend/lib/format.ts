/**
 * Display formatting for the measurement surfaces (run cost panel, analytics).
 *
 * Shared rather than inlined because the two views must agree: a run that reads
 * "12,480 tokens · $0.0031" on its own page and a different rounding of the same
 * number in the workspace total reads as a bug in the accounting, not a
 * formatting choice.
 */

/** Thousands-separated integer. Token counts get large fast and are unreadable
 *  as a bare run of digits. */
export function formatTokens(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/**
 * USD, with enough precision to stay non-zero.
 *
 * Per-agent spend on cheap models lands in the fourth decimal place, so the
 * usual two-decimal currency format would round almost every real figure to
 * "$0.00" and make the panel look broken. Below a cent we show four decimals.
 */
export function formatUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

/** Seconds as "4m 12s" — a wall-clock figure people compare against their own
 *  patience, which minutes express and raw seconds don't. */
export function formatDuration(sec: number): string {
  const total = Math.round(sec);
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}
