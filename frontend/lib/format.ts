/**
 * Display formatting for the measurement surfaces (run cost panel, analytics).
 *
 * Shared rather than inlined so the two views round identically: the same figure
 * displayed two ways reads as an accounting bug.
 */

/** Thousands-separated integer, since token counts get large fast. */
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

/** Seconds as "4m 12s"; raw seconds read poorly above a minute. */
export function formatDuration(sec: number): string {
  const total = Math.round(sec);
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}
