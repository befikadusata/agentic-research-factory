"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import * as Dialog from "@radix-ui/react-dialog";
import { LoaderCircle, Trash2, X } from "lucide-react";
import { addWorkspaceMember, getWorkspaceMembers, removeWorkspaceMember } from "@/lib/api";
import type { Workspace, WorkspaceMember } from "@/lib/types";

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

function MemberListSkeleton() {
  return (
    <div role="status" aria-label="Loading workspace members" className="space-y-2">
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          aria-hidden
          className="animate-pulse rounded-md border border-border-subtle bg-surface-2 px-3 py-3"
        >
          <div className="h-4 w-2/3 rounded bg-surface-3" />
          <div className="mt-2 h-3 w-1/3 rounded bg-surface-3" />
        </div>
      ))}
      <span className="sr-only">Loading workspace members…</span>
    </div>
  );
}

export function ManageMembersModal({
  workspace,
  open,
  onOpenChange,
}: {
  workspace: Workspace;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: session } = useSession();
  // Mirrors the backend's two independent grants: the admin role, or ownership.
  // Either alone is enough, so gating on both would hide controls the server
  // would have accepted.
  const mayManage = session?.user?.id === workspace.owner_id || workspace.role === "admin";

  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const [email, setEmail] = useState("");
  const [provider, setProvider] = useState("google");
  const [role, setRole] = useState("viewer");
  const [adding, setAdding] = useState(false);
  const [pendingRemoval, setPendingRemoval] = useState<WorkspaceMember | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setMembers(await getWorkspaceMembers(workspace.id));
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Failed to load members");
    } finally {
      setLoading(false);
    }
  }, [workspace.id]);

  useEffect(() => {
    if (open) {
      setActionError(null);
      setAnnouncement("");
      void load();
    }
  }, [load, open]);

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    setActionError(null);
    setAnnouncement("");
    setAdding(true);
    const normalizedEmail = email.trim().toLowerCase();
    try {
      await addWorkspaceMember(workspace.id, `${provider}:${normalizedEmail}`, role);
      setEmail("");
      setAnnouncement(`${normalizedEmail} was added to ${workspace.name}.`);
      await load();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to add member");
    } finally {
      setAdding(false);
    }
  }

  function requestRemoval(member: WorkspaceMember) {
    setRemoveError(null);
    setPendingRemoval(member);
  }

  async function handleRemove() {
    if (!pendingRemoval) return;
    const member = pendingRemoval;
    const { email: memberEmail } = parsePrincipal(member.user_id);
    setRemoveError(null);
    setAnnouncement("");
    setRemoving(true);
    try {
      await removeWorkspaceMember(workspace.id, member.user_id);
      setPendingRemoval(null);
      setAnnouncement(`${memberEmail} was removed from ${workspace.name}.`);
      await load();
    } catch (error) {
      setRemoveError(error instanceof Error ? error.message : "Failed to remove member");
    } finally {
      setRemoving(false);
    }
  }

  const mutationInProgress = adding || removing;
  const pendingRemovalEmail = pendingRemoval ? parsePrincipal(pendingRemoval.user_id).email : "this member";

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !mutationInProgress) onOpenChange(false);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-border-subtle bg-surface-1 p-5 shadow-xl sm:p-6">
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <Dialog.Title className="text-xl font-bold text-content">Workspace members</Dialog.Title>
              <Dialog.Description className="mt-1 truncate text-sm text-content-muted">
                Manage access to {workspace.name}.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={mutationInProgress}
                aria-label="Close member management"
                className="-m-2 flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-2 hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                <X size={19} aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          <p className="sr-only" aria-live="polite">{announcement}</p>

          <section aria-labelledby="workspace-member-list-heading" className="mt-5">
            <h3 id="workspace-member-list-heading" className="sr-only">Current members</h3>
            {loading ? (
              <MemberListSkeleton />
            ) : loadError ? (
              <div role="alert" className="rounded-md border border-feedback-error/40 bg-feedback-error/10 p-4">
                <p className="text-sm font-semibold text-content">Members couldn’t be loaded</p>
                <p className="mt-1 text-sm text-content-secondary">{loadError}</p>
                <button
                  type="button"
                  onClick={() => void load()}
                  className="mt-3 min-h-11 rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-content transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Retry
                </button>
              </div>
            ) : members.length === 0 ? (
              <div className="rounded-md border border-dashed border-border-subtle px-4 py-6 text-center text-sm text-content-muted">
                No members have been added yet.
              </div>
            ) : (
              <ul className="space-y-2">
                {members.map((member) => {
                  const { provider: memberProvider, email: memberEmail } = parsePrincipal(member.user_id);
                  const isWorkspaceOwner = member.user_id === workspace.owner_id;
                  return (
                    <li
                      key={member.user_id}
                      className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface-2 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-content" title={memberEmail}>{memberEmail}</p>
                        <p className="text-xs text-content-muted">
                          {PROVIDER_LABEL[memberProvider] ?? memberProvider} · {member.role}
                          {isWorkspaceOwner && " · owner"}
                        </p>
                      </div>
                      {mayManage && !isWorkspaceOwner && (
                        <button
                          type="button"
                          onClick={() => requestRemoval(member)}
                          aria-label={`Remove ${memberEmail}`}
                          className="-my-1 flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-feedback-error/10 hover:text-feedback-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                        >
                          <Trash2 size={17} aria-hidden />
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {mayManage ? (
            <form onSubmit={handleAdd} className="mt-6 space-y-4 border-t border-border-subtle pt-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-content-secondary">Add a member</h3>

              {actionError && (
                <p role="alert" className="rounded-md border border-feedback-error/40 bg-feedback-error/10 px-3 py-2 text-sm text-content">
                  {actionError}
                </p>
              )}

              <div>
                <label htmlFor="member-email" className="mb-1.5 block text-sm font-medium text-content">Email address</label>
                <input
                  id="member-email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="teammate@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={adding}
                  className="min-h-11 w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2 text-base text-content placeholder:text-content-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60 sm:text-sm"
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="member-provider" className="mb-1.5 block text-sm font-medium text-content">Sign-in method</label>
                  <select
                    id="member-provider"
                    value={provider}
                    onChange={(event) => setProvider(event.target.value)}
                    disabled={adding}
                    className="min-h-11 w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2 text-base text-content focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60 sm:text-sm"
                  >
                    {PROVIDERS.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="member-role" className="mb-1.5 block text-sm font-medium text-content">Workspace role</label>
                  <select
                    id="member-role"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                    disabled={adding}
                    className="min-h-11 w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2 text-base capitalize text-content focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60 sm:text-sm"
                  >
                    {ROLES.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </div>
              </div>

              <p className="text-xs leading-5 text-content-muted">
                Choose how this person signs in. Access is tied to that exact identity.
              </p>
              <button
                type="submit"
                disabled={adding || loading}
                className="flex min-h-11 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-on transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {adding ? (
                  <span className="flex items-center gap-2"><LoaderCircle size={16} className="animate-spin" aria-hidden /> Adding…</span>
                ) : "Add member"}
              </button>
            </form>
          ) : (
            <p className="mt-6 border-t border-border-subtle pt-4 text-xs leading-5 text-content-muted">
              Only workspace admins can add or remove members.
            </p>
          )}

          <Dialog.Root
            open={pendingRemoval !== null}
            onOpenChange={(nextOpen) => {
              if (!nextOpen && !removing) setPendingRemoval(null);
            }}
          >
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
              <Dialog.Content className="fixed left-1/2 top-1/2 z-[60] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border-subtle bg-surface-2 p-5 shadow-xl sm:p-6">
                <div className="flex items-start gap-4">
                  <div className="min-w-0 flex-1">
                    <Dialog.Title className="text-lg font-semibold text-content">Remove this member?</Dialog.Title>
                    <Dialog.Description className="mt-2 text-sm leading-6 text-content-secondary">
                      {pendingRemovalEmail} will lose access to {workspace.name}. You can add them again later.
                    </Dialog.Description>
                  </div>
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      disabled={removing}
                      aria-label="Close removal confirmation"
                      className="-m-2 flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-content-muted transition-colors hover:bg-surface-3 hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                    >
                      <X size={18} aria-hidden />
                    </button>
                  </Dialog.Close>
                </div>

                {removeError && (
                  <p role="alert" className="mt-4 rounded-md border border-feedback-error/40 bg-feedback-error/10 px-3 py-2 text-sm text-content">
                    {removeError}
                  </p>
                )}

                <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      disabled={removing}
                      className="min-h-11 rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-content transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                    >
                      Keep member
                    </button>
                  </Dialog.Close>
                  <button
                    type="button"
                    onClick={() => void handleRemove()}
                    disabled={removing}
                    className="min-h-11 rounded-md bg-feedback-error px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-feedback-error focus-visible:ring-offset-2 focus-visible:ring-offset-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {removing ? (
                      <span className="flex items-center justify-center gap-2"><LoaderCircle size={16} className="animate-spin" aria-hidden /> Removing…</span>
                    ) : "Remove member"}
                  </button>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
