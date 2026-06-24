import type { Run, RunDetail } from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL;

// Simple cache
const cache = new Map<string, { data: unknown; expires: number }>();
const CACHE_TTL = 30 * 1000; // 30 seconds

async function authHeaders(): Promise<Record<string, string>> {
  const res = await fetch("/api/backend-token");
  if (!res.ok) throw new Error("Failed to obtain backend auth token.");
  const { token } = await res.json();
  if (!token) throw new Error("Missing backend auth token.");
  return { Authorization: `Bearer ${token}` };
}

export async function createRun(payload: {
  topic: string;
  format: string;
  doc_ids: string[];
  vertical?: string;
  vertical_inputs?: Record<string, string>;
}): Promise<{ id: string }> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  // Invalidate runs list cache on new run
  cache.delete("runs");
  return res.json();
}

export async function getRuns(): Promise<Run[]> {
  const cached = cache.get("runs");
  if (cached && cached.expires > Date.now()) return cached.data as Run[];

  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs`, { headers });
  if (!res.ok) throw new Error(await res.text());
  
  const data = await res.json();
  cache.set("runs", { data, expires: Date.now() + CACHE_TTL });
  return data;
}

export async function getRun(id: string): Promise<RunDetail> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveHitl(id: string, instruction?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ instruction: instruction ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadFile(file: File): Promise<{ doc_id: string }> {
  const headers = await authHeaders();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", headers, body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getOutputUrl(runId: string, format: "pdf" | "md"): string {
  return `${BASE}/runs/${runId}/output/${format}`;
}
