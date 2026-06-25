"use client";

import { useSession, signOut } from "next-auth/react";
import { LogOut } from "lucide-react";

export function SidebarUser() {
  const { data: session } = useSession();
  if (!session?.user) return null;

  return (
    <div className="border-t border-zinc-800 pt-4">
      <div className="flex items-center gap-3 mb-3 px-1">
        {session.user.image && (
          // Plain img — next/image requires remotePatterns config for lh3.googleusercontent.com
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={session.user.image}
            alt=""
            referrerPolicy="no-referrer"
            className="w-8 h-8 rounded-full flex-shrink-0"
          />
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-200 truncate">{session.user.name}</p>
          <p className="text-xs text-zinc-500 truncate">{session.user.email}</p>
        </div>
      </div>
      <button
        onClick={() => signOut({ callbackUrl: "/" })}
        className="w-full flex items-center gap-2 text-sm text-zinc-400 hover:text-white px-2 py-2 rounded-lg hover:bg-zinc-800 transition-colors"
      >
        <LogOut size={16} />
        Sign out
      </button>
    </div>
  );
}
