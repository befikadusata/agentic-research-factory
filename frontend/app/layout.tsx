import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import "./globals.css";
import { SessionProvider } from "./providers";
import { AppShell } from "@/components/AppShell";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Agentic Research Factory",
  description: "AI-powered research pipeline",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions);
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable}`}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem("ftm-theme")==="light"){document.documentElement.classList.add("light")}}catch(e){}`,
          }}
        />
      </head>
      <body className="bg-surface-0 text-content min-h-screen">
        <SessionProvider session={session}>
          <AppShell>{children}</AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}
