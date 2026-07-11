"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { getWorkspaceMembers, addWorkspaceMember, removeWorkspaceMember } from "@/lib/api";
import type { Workspace, WorkspaceMember } from "@/lib/types";
import { X, Trash2 } from "lucide-react";

const PROVIDERS = [
  { value: "google", label: "Google" },
  { value: "credentials", label: "Email / password" },
];
const ROLES = ["viewer", "operator", "admin"];

function parsePrincipal(id: string): { provider: string; email: string } {
  const idx = id.indexOf(":");
  if (idx === -1) return { provider: "unknown", email: id };
  return { provider: id.slice(0, idx), email: id.slice(idx + 1) };
}

const PROVIDER_LABEL: Record<string, string> = { google: "Google", credentials: "Email" };

export function ManageMembersModal({
  workspace,
  onClose,
}: {
  workspace: Workspace;
  onClose: () => void;
}) {
  const { data: session } = useSession();
  const isOwner = session?.user?.id === workspace.owner_id;

  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [provider, setProvider] = useState("google");
  const [role, setRole] = useState("viewer");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMembers(await getWorkspaceMembers(workspace.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load members");
    } finally {
      setLoading(false);
    }
  }, [workspace.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await addWorkspaceMember(workspace.id, `${provider}:${email.trim().toLowerCase()}`, role);
      setEmail("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add member");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(userId: string) {
    setError(null);
    try {
      await removeWorkspaceMember(workspace.id, userId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove member");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-surface-1 border border-border-subtle rounded-xl p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-xl font-bold text-content">Members</h2>
          <button onClick={onClose} aria-label="Close" className="text-content-muted hover:text-content">
            <X size={20} />
          </button>
        </div>
        <p className="text-sm text-content-muted mb-5">{workspace.name}</p>

        {error && (
          <p className="text-sm text-feedback-error bg-feedback-error/10 border border-feedback-error/40 rounded-md px-3 py-2 mb-4">
            {error}
          </p>
        )}

        <div className="space-y-2 mb-6">
          {loading ? (
            <p className="text-content-muted text-sm">Loading…</p>
          ) : (
            members.map((m) => {
              const { provider: prov, email: mEmail } = parsePrincipal(m.user_id);
              const isWsOwner = m.user_id === workspace.owner_id;
              return (
                <div
                  key={m.user_id}
                  className="flex items-center justify-between bg-surface-2 border border-border-subtle rounded-md px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-content font-medium truncate">{mEmail}</p>
                    <p className="text-xs text-content-muted">
                      {PROVIDER_LABEL[prov] ?? prov} · {m.role}
                      {isWsOwner && " · owner"}
                    </p>
                  </div>
                  {isOwner && !isWsOwner && (
                    <button
                      onClick={() => handleRemove(m.user_id)}
                      aria-label={`Remove ${mEmail}`}
                      className="text-content-muted hover:text-feedback-error flex-shrink-0 ml-3"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        {isOwner ? (
          <form onSubmit={handleAdd} className="border-t border-border-subtle pt-5 space-y-3">
            <p className="text-xs font-bold text-content-secondary uppercase tracking-wider">Invite a member</p>
            <input
              type="email"
              required
              placeholder="teammate@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-surface-2 border border-border-subtle text-content placeholder:text-content-muted focus:outline-none focus:border-primary text-sm"
            />
            <div className="flex gap-2">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="flex-1 px-3 py-2 rounded-md bg-surface-2 border border-border-subtle text-content text-sm focus:outline-none focus:border-primary"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="flex-1 px-3 py-2 rounded-md bg-surface-2 border border-border-subtle text-content text-sm focus:outline-none focus:border-primary capitalize"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <p className="text-xs text-content-muted">
              Choose how this person signs in — access is scoped to that identity.
            </p>
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-primary hover:bg-primary-hover text-primary-on font-medium py-2 rounded-md transition-colors disabled:opacity-60 text-sm"
            >
              {busy ? "Adding…" : "Add member"}
            </button>
          </form>
        ) : (
          <p className="text-xs text-content-muted border-t border-border-subtle pt-4">
            Only the workspace owner can add or remove members.
          </p>
        )}
      </div>
    </div>
  );
}
