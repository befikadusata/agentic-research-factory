import type { Metadata } from "next";
import Link from "next/link";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SessionProvider } from "./providers";
import { LayoutGrid, Plus, History } from "lucide-react";
import { SidebarUser } from "@/components/SidebarUser";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Agentic Research Factory",
  description: "AI-powered research pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable}`}>
      <body className="bg-surface-0 text-content min-h-screen flex">
        <SessionProvider>
          {/* Sidebar */}
          <aside className="w-64 border-r border-border-subtle p-6 flex flex-col gap-6 min-h-screen bg-surface-1">
            <Link href="/" className="font-bold text-primary text-xl flex items-center gap-2">
              <LayoutGrid size={24} />
              Research Factory
            </Link>
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
