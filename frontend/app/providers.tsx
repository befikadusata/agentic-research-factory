"use client";

import { SessionProvider as NextAuthSessionProvider } from "next-auth/react";
import type { Session } from "next-auth";
import { WorkspaceProvider } from "@/lib/workspace";

export function SessionProvider({
  children,
  session,
}: {
  children: React.ReactNode;
  session: Session | null;
}) {
  return (
    <NextAuthSessionProvider session={session}>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </NextAuthSessionProvider>
  );
}
