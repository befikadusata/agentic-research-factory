import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { SessionProvider } from "./providers";
import { LayoutGrid, Plus, History } from "lucide-react";
import { SidebarUser } from "@/components/SidebarUser";

export const metadata: Metadata = {
  title: "Agentic Research Factory",
  description: "AI-powered research pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen flex">
        <SessionProvider>
          {/* Sidebar */}
          <aside className="w-64 border-r border-zinc-800 p-6 flex flex-col gap-6 min-h-screen">
            <Link href="/" className="font-bold text-primary-500 text-xl flex items-center gap-2">
              <LayoutGrid size={24} />
              Research Factory
            </Link>
            <Link
              href="/new"
              className="bg-cta hover:bg-green-600 text-white font-medium px-4 py-2 rounded-lg flex items-center justify-center gap-2"
            >
              <Plus size={18} />
              New Run
            </Link>
            <nav className="flex flex-col gap-2">
              <Link href="/" className="text-zinc-400 hover:text-white px-4 py-2 rounded-lg flex items-center gap-3">
                <History size={18} />
                History
              </Link>
            </nav>
            <div className="mt-auto">
              <SidebarUser />
            </div>
          </aside>
          
          {/* Main content */}
          <main className="flex-1 px-8 py-8">{children}</main>
        </SessionProvider>
      </body>
    </html>
  );
}
