"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { LayoutGrid, Plus, History, Radar, Menu, X } from "lucide-react";
import { SidebarUser } from "@/components/SidebarUser";
import { ThemeToggle } from "@/components/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { AuthScreen } from "@/components/AuthScreen";

// Routes that render for signed-out users without the app chrome (e.g. the
// email verification link lands here before the user has a session).
const PUBLIC_ROUTES = ["/verify-email"];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const historyActive = pathname === "/";
  const newRunActive = pathname === "/new";
  const monitorsActive = pathname?.startsWith("/monitors");

  return (
    <>
      <Link
        href="/"
        onClick={onNavigate}
        className="font-bold text-primary text-xl flex items-center gap-2"
      >
        <LayoutGrid size={24} />
        Research Factory
      </Link>
      <WorkspaceSwitcher />
      <Link
        href="/new"
        onClick={onNavigate}
        aria-current={newRunActive ? "page" : undefined}
        className={`min-h-11 border font-medium px-4 py-2 rounded-md flex items-center justify-center gap-2 transition-colors duration-base ${
          newRunActive
            ? "border-primary bg-primary text-primary-on"
            : "border-transparent bg-primary hover:bg-primary-hover text-primary-on"
        }`}
      >
        <Plus size={18} />
        New Run
      </Link>
      <nav className="flex flex-col gap-2" aria-label="Primary navigation">
        <Link
          href="/"
          onClick={onNavigate}
          aria-current={historyActive ? "page" : undefined}
          className={`min-h-11 px-4 py-2 rounded-md flex items-center gap-3 transition-colors ${
            historyActive
              ? "bg-surface-3 text-content"
              : "text-content-secondary hover:bg-surface-2 hover:text-content"
          }`}
        >
          <History size={18} />
          History
        </Link>
        <Link
          href="/monitors"
          onClick={onNavigate}
          aria-current={monitorsActive ? "page" : undefined}
          className={`min-h-11 px-4 py-2 rounded-md flex items-center gap-3 transition-colors ${
            monitorsActive
              ? "bg-surface-3 text-content"
              : "text-content-secondary hover:bg-surface-2 hover:text-content"
          }`}
        >
          <Radar size={18} />
          Monitors
        </Link>
      </nav>
      <div className="mt-auto flex flex-col gap-2">
        <ThemeToggle />
        <SidebarUser />
      </div>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const pathname = usePathname();
  const isPublic = PUBLIC_ROUTES.some((r) => pathname?.startsWith(r));
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

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
    <div className="min-h-screen lg:flex">
      <a
        href="#main-content"
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-md bg-primary px-4 py-2 font-semibold text-primary-on transition-transform focus:translate-y-0"
      >
        Skip to main content
      </a>
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border-subtle bg-surface-1 px-4 lg:hidden">
        <Link href="/" className="flex items-center gap-2 font-bold text-primary">
          <LayoutGrid size={22} />
          Research Factory
        </Link>
        <Dialog.Root open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <Dialog.Trigger asChild>
            <button
              type="button"
              className="flex size-11 items-center justify-center rounded-md text-content-secondary transition-colors hover:bg-surface-3 hover:text-content"
              aria-label="Open navigation"
            >
              <Menu size={22} />
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-surface-0/80 backdrop-blur-sm" />
            <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(20rem,calc(100vw-3rem))] flex-col gap-6 overflow-y-auto border-r border-border-subtle bg-surface-1 p-6 shadow-hairline">
              <div className="flex items-center justify-between gap-4">
                <Dialog.Title className="sr-only">Application navigation</Dialog.Title>
                <span className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                  Navigation
                </span>
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="flex size-11 items-center justify-center rounded-md text-content-secondary transition-colors hover:bg-surface-3 hover:text-content"
                    aria-label="Close navigation"
                  >
                    <X size={22} />
                  </button>
                </Dialog.Close>
              </div>
              <SidebarContent onNavigate={() => setMobileNavOpen(false)} />
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </header>

      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-border-subtle bg-surface-1 p-6 lg:flex">
        <SidebarContent />
      </aside>

      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 sm:px-6 md:px-8 md:py-8">
        {children}
      </main>
    </div>
  );
}
