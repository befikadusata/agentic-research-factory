"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { getWorkspaces } from "@/lib/api";
import type { Workspace } from "@/lib/types";

const STORAGE_KEY = "rf-active-workspace";

interface WorkspaceContextValue {
  workspaces: Workspace[];
  active: Workspace | null;
  activeId: string | null;
  setActiveId: (id: string) => void;
  /** Reload the workspace list; optionally make `selectId` active afterwards. */
  refresh: (selectId?: string) => Promise<void>;
  loading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const setActiveId = useCallback((id: string) => {
    setActiveIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore storage failures */
    }
  }, []);

  const refresh = useCallback(
    async (selectId?: string) => {
      const ws = await getWorkspaces();
      setWorkspaces(ws);
      const stored = (() => {
        try {
          return localStorage.getItem(STORAGE_KEY);
        } catch {
          return null;
        }
      })();
      const preferred = selectId ?? stored;
      const valid = ws.find((w) => w.id === preferred) ?? ws[0] ?? null;
      if (valid) setActiveId(valid.id);
    },
    [setActiveId],
  );

  useEffect(() => {
    if (status !== "authenticated") {
      setLoading(false);
      return;
    }
    setLoading(true);
    refresh().finally(() => setLoading(false));
  }, [status, refresh]);

  const active = workspaces.find((w) => w.id === activeId) ?? null;

  return (
    <WorkspaceContext.Provider
      value={{ workspaces, active, activeId, setActiveId, refresh, loading }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return ctx;
}
