"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CircleAlert, CircleCheck } from "lucide-react";
import { AuthLoadingState } from "@/components/AuthLoadingState";

type State = "verifying" | "success" | "error";

function VerificationResult({
  state,
  email,
}: {
  state: Exclude<State, "verifying">;
  email: string | null;
}) {
  const successful = state === "success";

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4 py-10">
      <div
        role={successful ? "status" : "alert"}
        aria-live={successful ? "polite" : "assertive"}
        className="w-full max-w-md rounded-xl border border-border-subtle bg-surface-1 p-6 text-center shadow-hairline sm:p-8"
      >
        <div
          className={`mx-auto flex h-14 w-14 items-center justify-center rounded-full border ${
            successful
              ? "border-feedback-success/40 bg-feedback-success/10 text-feedback-success"
              : "border-feedback-error/40 bg-feedback-error/10 text-feedback-error"
          }`}
        >
          {successful ? <CircleCheck size={28} aria-hidden /> : <CircleAlert size={28} aria-hidden />}
        </div>
        <h1 className="mt-5 text-2xl font-bold text-content sm:text-3xl">
          {successful ? "Email verified" : "Verification failed"}
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-content-secondary sm:text-base">
          {successful ? (
            <>
              {email ? <><span className="break-all font-medium text-content">{email}</span> is confirmed. </> : null}
              You can now sign in to your workspace.
            </>
          ) : (
            "This verification link is invalid or has expired. Return to sign in and request a new one."
          )}
        </p>
        <Link
          href="/"
          className={`mt-7 inline-flex min-h-11 items-center justify-center rounded-md px-6 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1 ${
            successful
              ? "bg-primary text-primary-on hover:bg-primary-hover"
              : "border border-border-subtle bg-surface-2 text-content hover:bg-surface-3"
          }`}
        >
          {successful ? "Continue to sign in" : "Back to sign in"}
        </Link>
      </div>
    </div>
  );
}

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

    const controller = new AbortController();

    (async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/auth/verify-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
          signal: controller.signal,
        });
        if (!response.ok) {
          setState("error");
          return;
        }
        const data = await response.json();
        setEmail(data.email ?? null);
        setState("success");
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setState("error");
      }
    })();

    return () => controller.abort();
  }, [token]);

  if (state === "verifying") {
    return (
      <AuthLoadingState
        title="Verifying your email"
        description="Checking your secure verification link. This should only take a moment."
      />
    );
  }

  return <VerificationResult state={state} email={email} />;
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={(
        <AuthLoadingState
          title="Preparing email verification"
          description="Loading your secure verification link."
        />
      )}
    >
      <VerifyEmailInner />
    </Suspense>
  );
}
