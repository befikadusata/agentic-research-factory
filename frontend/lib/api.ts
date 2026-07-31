import type {
  AnalyticsCosts,
  AnalyticsMetrics,
  CreateMonitorInput,
  DocumentState,
  Monitor,
  Run,
  RunDetail,
  Workspace,
  WorkspaceMember,
} from "./types";
import { normalizeLogEntries } from "./logs";
import { IS_DEMO, demoApi } from "./demo";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL;

// Demo mode (NEXT_PUBLIC_DEMO=1) swaps every call below for the in-memory seed
// in `lib/demo.ts`, so the app runs with no backend and no API keys. The guards
// are written out one per function rather than hidden behind a wrapper: this is
// the file where "does this reach the network?" has to be answerable by reading
// it.
//
// IS_DEMO is inlined at build time, so a normal build never takes these
// branches — but it does still bundle the seed (~24 kB of fixture text in a
// shared chunk), because `demoApi` is a static import. That is a size cost, not
// a correctness one: unreachable sample markdown. Removing it would mean
// dynamic imports in five call sites, two of which are synchronous render
// paths, which is a worse trade than the kilobytes are worth.

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
  if (IS_DEMO) return demoApi.authHeaders();
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
  if (IS_DEMO) return demoApi.createRun(payload);
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
  if (IS_DEMO) return demoApi.getRuns(workspaceId);
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
  if (IS_DEMO) return demoApi.getRun(id);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/runs/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json() as RunDetail;
  return { ...data, logs: normalizeLogEntries(data.logs) };
}

export async function approveHitl(id: string, instruction?: string) {
  if (IS_DEMO) return demoApi.approveHitl(id, instruction);
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
  if (IS_DEMO) return demoApi.uploadFile(file, workspaceId);
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

/** Current ingest state of an uploaded doc. `uploadFile` returns as soon as the
 *  file is stored — parsing and chunking run in a Celery worker afterwards — so
 *  this is the only way to know whether the doc is actually retrievable yet. */
export async function getDocument(docId: string): Promise<DocumentState> {
  if (IS_DEMO) return demoApi.getDocument(docId);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/upload/${docId}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// --- Analytics ------------------------------------------------------------
// Both endpoints scope to a workspace the caller belongs to, or — with no
// workspace_id — to the caller's own runs. The UI always has an active
// workspace, so it always passes one.

export async function getAnalyticsMetrics(workspaceId?: string): Promise<AnalyticsMetrics> {
  if (IS_DEMO) return demoApi.getAnalyticsMetrics(workspaceId);
  const headers = await authHeaders();
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
  const res = await fetch(`${BASE}/analytics/metrics${qs}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAnalyticsCosts(workspaceId?: string): Promise<AnalyticsCosts> {
  if (IS_DEMO) return demoApi.getAnalyticsCosts(workspaceId);
  const headers = await authHeaders();
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
  const res = await fetch(`${BASE}/analytics/costs${qs}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// --- Workspaces -----------------------------------------------------------

export async function getWorkspaces(): Promise<Workspace[]> {
  if (IS_DEMO) return demoApi.getWorkspaces();
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createWorkspace(name: string): Promise<Workspace> {
  if (IS_DEMO) return demoApi.createWorkspace(name);
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
  if (IS_DEMO) return demoApi.getWorkspaceMembers(workspaceId);
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
  if (IS_DEMO) return demoApi.addWorkspaceMember(workspaceId, userId, role);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ user_id: userId, role }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
  if (IS_DEMO) return demoApi.removeWorkspaceMember(workspaceId, userId);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/members/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers,
  });
  if (!res.ok) throw new Error(await res.text());
}

// --- Monitors -------------------------------------------------------------

export async function getMonitors(workspaceId?: string): Promise<Monitor[]> {
  if (IS_DEMO) return demoApi.getMonitors(workspaceId);
  const headers = await authHeaders();
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
  const res = await fetch(`${BASE}/monitors${qs}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMonitor(id: string): Promise<Monitor> {
  if (IS_DEMO) return demoApi.getMonitor(id);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMonitorRuns(id: string): Promise<Run[]> {
  if (IS_DEMO) return demoApi.getMonitorRuns(id);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}/runs`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createMonitor(payload: CreateMonitorInput): Promise<Monitor> {
  if (IS_DEMO) return demoApi.createMonitor(payload);
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
  if (IS_DEMO) return demoApi.updateMonitor(id, patch);
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
  if (IS_DEMO) return demoApi.runMonitorNow(id);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}/run`, { method: "POST", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteMonitor(id: string): Promise<void> {
  if (IS_DEMO) return demoApi.deleteMonitor(id);
  const headers = await authHeaders();
  const res = await fetch(`${BASE}/monitors/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(await res.text());
}

export async function downloadOutput(
  runId: string,
  format: "pdf" | "md",
): Promise<void> {
  if (IS_DEMO) return demoApi.downloadOutput(runId, format);
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
