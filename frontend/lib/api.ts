import type { Run, RunDetail, Workspace, WorkspaceMember, Monitor, CreateMonitorInput } from "./types";
import { normalizeLogEntries } from "./logs";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL;

// Simple cache
const cache = new Map<string, { data: unknown; expires: number }>();
const CACHE_TTL = 30 * 1000; // 30 seconds

let cachedAuth: { token: string; expiresAt: number } | null = null;
const TOKEN_REFRESH_MARGIN = 30 * 1000; // refresh this long before actual expiry

function decodeJwtExpiry(token: string): number {
  try {
    const payload = token.split(".")[1];
    const { exp } = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return exp * 1000;
  } catch {
    // Token isn't a decodable JWT — don't cache it (expire immediately) so the
    // next call re-fetches, rather than crashing every authenticated request.
    return 0;
  }
}

export async function authHeaders(): Promise<Record<string, string>> {
  if (cachedAuth && cachedAuth.expiresAt - TOKEN_REFRESH_MARGIN > Date.now()) {
    return { Authorization: `Bearer ${cachedAuth.token}` };
  }
  const res = await fetch("/api/backend-token");
  if (!res.ok) throw new Error("Failed to obtain backend auth token.");
  const { token } = await res.json();
  if (!token) throw new Error("Missing backend auth token.");
  cachedAuth = { token, expiresAt: decodeJwtExpiry(token) };
  return { Authorization: `Bearer ${token}` };
}

export async function createRun(payload: {
  topic: string;
  format: string;
  doc_ids: string[];
  workspace_id?: string;
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
  cache.clear();
  return res.json();
}

export async function getRuns(workspaceId?: string): Promise<Run[]> {
  const key = `runs:${workspaceId ?? "personal"}`;
  const cached = cache.get(key);
  if (cached && cached.expires > Date.now()) return cached.data as Run[];

  const headers = await authHeaders();
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
  const res = await fetch(`${BASE}/runs${qs}`, { headers });
  if (!res.ok) throw new Error(await res.text());

  const data = await res.json();
  cache.set(key, { data, expires: Date.now() + CACHE_TTL });
  return data;
}

export async function getRun(id: string): Promise<RunDetail> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json() as RunDetail;
  return { ...data, logs: normalizeLogEntries(data.logs) };
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

export async function uploadFile(file: File, workspaceId: string): Promise<{ doc_id: string }> {
  const headers = await authHeaders();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload?workspace_id=${workspaceId}`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// --- Workspaces -----------------------------------------------------------

export async function getWorkspaces(): Promise<Workspace[]> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createWorkspace(name: string): Promise<Workspace> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/members`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addWorkspaceMember(
  workspaceId: string,
  userId: string,
  role: string,
): Promise<void> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ user_id: userId, role }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/members/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers,
  });
  if (!res.ok) throw new Error(await res.text());
}

// --- Monitors -------------------------------------------------------------

export async function getMonitors(workspaceId?: string): Promise<Monitor[]> {
  const headers = await authHeaders();
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
  const res = await fetch(`${BASE}/monitors${qs}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMonitor(id: string): Promise<Monitor> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMonitorRuns(id: string): Promise<Run[]> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}/runs`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createMonitor(payload: CreateMonitorInput): Promise<Monitor> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateMonitor(
  id: string,
  patch: Partial<Pick<Monitor, "name" | "interval_minutes" | "enabled" | "notify_channel">>,
): Promise<Monitor> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function runMonitorNow(id: string): Promise<{ id: string }> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}/run`, { method: "POST", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteMonitor(id: string): Promise<void> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(await res.text());
}

export async function downloadOutput(
  runId: string,
  format: "pdf" | "md",
): Promise<void> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${runId}/output/${format}`, { headers });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `report_${runId}.${format}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
