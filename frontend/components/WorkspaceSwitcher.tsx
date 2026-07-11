"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useWorkspace } from "@/lib/workspace";
import { createWorkspace } from "@/lib/api";
import { ManageMembersModal } from "@/components/ManageMembersModal";
import { Check, ChevronsUpDown, Plus, Users } from "lucide-react";

export function WorkspaceSwitcher() {
  const { status } = useSession();
  const { workspaces, active, setActiveId, refresh, loading } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [showMembers, setShowMembers] = useState(false);

  if (status !== "authenticated") return null;
  if (loading && !active) {
    return <div className="text-xs text-content-muted px-3 py-2">Loading workspace…</div>;
  }
  if (!active) return null;

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setBusy(true);
    try {
      const ws = await createWorkspace(newName.trim());
      await refresh(ws.id);
      setNewName("");
      setCreating(false);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-md px-3 py-2 text-sm text-content transition-colors"
      >
        <span className="truncate font-medium">{active.name}</span>
        <ChevronsUpDown size={15} className="text-content-muted flex-shrink-0" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => { setOpen(false); setCreating(false); }} />
          <div className="absolute z-20 mt-1 w-full bg-surface-1 border border-border-subtle rounded-md shadow-lg py-1">
            <div className="max-h-56 overflow-y-auto">
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={() => { setActiveId(ws.id); setOpen(false); }}
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm text-content hover:bg-surface-2 transition-colors"
                >
                  <span className="truncate">{ws.name}</span>
                  {ws.id === active.id && <Check size={15} className="text-primary flex-shrink-0" />}
                </button>
              ))}
            </div>

            <div className="border-t border-border-subtle mt-1 pt-1">
              <button
                onClick={() => { setShowMembers(true); setOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-content-secondary hover:text-content hover:bg-surface-2 transition-colors"
              >
                <Users size={15} /> Manage members
              </button>

              {creating ? (
                <form onSubmit={handleCreate} className="px-3 py-2">
                  <input
                    autoFocus
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Workspace name"
                    className="w-full px-2 py-1.5 rounded bg-surface-2 border border-border-subtle text-content text-sm placeholder:text-content-muted focus:outline-none focus:border-primary"
                  />
                  <button
                    type="submit"
                    disabled={busy}
                    className="w-full mt-2 bg-primary hover:bg-primary-hover text-primary-on text-sm font-medium py-1.5 rounded disabled:opacity-60"
                  >
                    {busy ? "Creating…" : "Create"}
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setCreating(true)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-content-secondary hover:text-content hover:bg-surface-2 transition-colors"
                >
                  <Plus size={15} /> New workspace
                </button>
              )}
            </div>
          </div>
        </>
      )}

      {showMembers && <ManageMembersModal workspace={active} onClose={() => setShowMembers(false)} />}
    </div>
  );
}
