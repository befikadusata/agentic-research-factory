import type { LogEntry } from "./types";

function displayString(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return null;
  }
}

export function normalizeLogEntry(value: unknown): LogEntry | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const entry = value as Record<string, unknown>;
  const eventType = displayString(entry.type) ?? "log";
  const payload = entry.data && typeof entry.data === "object" && !Array.isArray(entry.data)
    ? entry.data as Record<string, unknown>
    : entry;

  let message = displayString(payload.message);
  if (!message && eventType === "status") {
    const status = displayString(payload.status);
    if (status) message = `Status changed to ${status}`;
  } else if (!message && eventType === "hitl_required") {
    const stage = displayString(payload.stage);
    if (stage) message = `Human approval required at ${stage}`;
  } else if (!message && eventType === "complete") {
    message = "Run completed";
  }
  if (!message) return null;

  return {
    agent: displayString(payload.agent) ?? (eventType === "error" ? "error" : "system"),
    message,
    ts: displayString(entry.ts) ?? displayString(payload.ts) ?? "",
  };
}

export function normalizeLogEntries(value: unknown): LogEntry[] {
  return Array.isArray(value)
    ? value.map(normalizeLogEntry).filter((entry): entry is LogEntry => entry !== null)
    : [];
}
