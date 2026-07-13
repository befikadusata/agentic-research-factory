"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { LayoutGrid, Plus, History, Radar } from "lucide-react";
import { SidebarUser } from "@/components/SidebarUser";
import { ThemeToggle } from "@/components/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { AuthScreen } from "@/components/AuthScreen";

// Routes that render for signed-out users without the app chrome (e.g. the
// email verification link lands here before the user has a session).
const PUBLIC_ROUTES = ["/verify-email"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const pathname = usePathname();
  const isPublic = PUBLIC_ROUTES.some((r) => pathname?.startsWith(r));

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center text-content-muted">
        Loading…
      </div>
    );
  }

  if (status === "unauthenticated") {
    if (isPublic) {
      return <main className="min-h-screen">{children}</main>;
    }
    return <AuthScreen />;
  }

  // Authenticated → full application shell.
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 border-r border-border-subtle p-6 flex flex-col gap-6 min-h-screen bg-surface-1">
        <Link href="/" className="font-bold text-primary text-xl flex items-center gap-2">
          <LayoutGrid size={24} />
          Research Factory
        </Link>
        <WorkspaceSwitcher />
        <Link
          href="/new"
          className="bg-primary hover:bg-primary-hover text-primary-on font-medium px-4 py-2 rounded-md flex items-center justify-center gap-2 transition-colors duration-base"
        >
          <Plus size={18} />
          New Run
        </Link>
        <nav className="flex flex-col gap-2">
          <Link href="/" className="text-content-secondary hover:text-content px-4 py-2 rounded-md flex items-center gap-3 transition-colors">
            <History size={18} />
            History
          </Link>
          <Link href="/monitors" className="text-content-secondary hover:text-content px-4 py-2 rounded-md flex items-center gap-3 transition-colors">
            <Radar size={18} />
            Monitors
          </Link>
        </nav>
        <div className="mt-auto flex flex-col gap-2">
          <ThemeToggle />
          <SidebarUser />
        </div>
      </aside>

      <main className="flex-1 px-8 py-8">{children}</main>
    </div>
  );
}
