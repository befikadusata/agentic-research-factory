"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

type State = "verifying" | "success" | "error";

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<State>("verifying");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }
    (async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/auth/verify-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!res.ok) {
          setState("error");
          return;
        }
        const data = await res.json();
        setEmail(data.email ?? null);
        setState("success");
      } catch {
        setState("error");
      }
    })();
  }, [token]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      {state === "verifying" && (
        <p className="text-content-muted">Verifying your email…</p>
      )}
      {state === "success" && (
        <>
          <h1 className="text-3xl font-bold mb-3 text-content">Email verified ✓</h1>
          <p className="text-content-secondary mb-8 max-w-md">
            {email ? <><span className="font-medium text-content">{email}</span> is confirmed. </> : null}
            You can now sign in.
          </p>
          <Link
            href="/"
            className="bg-primary hover:bg-primary-hover text-primary-on font-medium px-8 py-3 rounded-md transition-colors duration-base"
          >
            Go to sign in
          </Link>
        </>
      )}
      {state === "error" && (
        <>
          <h1 className="text-3xl font-bold mb-3 text-content">Verification failed</h1>
          <p className="text-content-secondary mb-8 max-w-md">
            This verification link is invalid or has expired. Sign in and request a new one.
          </p>
          <Link
            href="/"
            className="bg-surface-2 hover:bg-surface-3 border border-border-subtle text-content font-medium px-8 py-3 rounded-md transition-colors duration-base"
          >
            Back to sign in
          </Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="text-content-muted p-8">Loading…</p>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
