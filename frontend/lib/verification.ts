/** The single call site for POST /auth/resend-verification.
 *
 * Two screens ask for a fresh link — the sign-in form and the dead end you
 * reach from an expired one — and they must not drift apart on what the
 * response means.
 */
export type ResendResult = { devVerificationUrl: string | null };

/**
 * Request a new verification email.
 *
 * The endpoint answers 200 whether or not the address has an unverified
 * account, so that it cannot be used to test which emails are registered.
 * Success here therefore means "the request was accepted" and nothing more —
 * callers must phrase their confirmation conditionally rather than claiming a
 * mail was sent. `dev_verification_url` is populated outside production only.
 */
export async function resendVerification(email: string): Promise<ResendResult> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error("RESEND_FAILED");
  const data = await res.json().catch(() => ({}));
  return { devVerificationUrl: data.dev_verification_url ?? null };
}
