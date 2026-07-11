"use client";

import { signIn } from "next-auth/react";
import { LayoutGrid } from "lucide-react";
import { CredentialsForm } from "@/components/CredentialsForm";

export function AuthScreen() {
  return (
    <div className="min-h-screen grid md:grid-cols-2">
      {/* Brand / value panel (hidden on small screens) */}
      <div className="hidden md:flex flex-col justify-between p-12 bg-surface-1 border-r border-border-subtle">
        <div className="flex items-center gap-2 text-primary font-bold text-xl">
          <LayoutGrid size={26} />
          Research Factory
        </div>

        <div>
          <h1 className="text-4xl font-bold text-content leading-tight mb-4">
            Autonomous research,
            <br />
            powered by agents.
          </h1>
          <p className="text-content-secondary max-w-md mb-8">
            A multi-agent pipeline that researches, analyzes, and writes — with a
            human in the loop at every critical step.
          </p>
          <ul className="space-y-3 text-content-secondary text-sm">
            <li className="flex items-center gap-2"><span className="text-primary">◆</span> Multi-agent research → analysis → writing</li>
            <li className="flex items-center gap-2"><span className="text-primary">◆</span> Human-in-the-loop approval gates</li>
            <li className="flex items-center gap-2"><span className="text-primary">◆</span> Workspaces &amp; shared runs for your team</li>
          </ul>
        </div>

        <p className="text-content-muted text-xs">© Research Factory</p>
      </div>

      {/* Form panel */}
      <div className="flex flex-col items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="md:hidden flex items-center justify-center gap-2 text-primary font-bold text-xl mb-8">
            <LayoutGrid size={24} />
            Research Factory
          </div>

          <h2 className="text-2xl font-bold text-content mb-1">Welcome back</h2>
          <p className="text-content-secondary text-sm mb-6">Sign in to continue.</p>

          <CredentialsForm />

          <div className="flex items-center gap-3 my-6">
            <span className="h-px flex-1 bg-border-subtle" />
            <span className="text-xs text-content-muted uppercase tracking-wider">or</span>
            <span className="h-px flex-1 bg-border-subtle" />
          </div>

          <button
            onClick={() => signIn("google")}
            className="w-full bg-surface-2 hover:bg-surface-3 border border-border-subtle text-content font-medium px-8 py-3 rounded-md transition-colors duration-base"
          >
            Sign in with Google
          </button>
        </div>
      </div>
    </div>
  );
}
