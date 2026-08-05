/** The single call site for POST /auth/resend-verification, shared by the
 *  sign-in form and the expired-link dead end so the two cannot drift apart on
 *  what the response means. */
export type ResendResult = { devVerificationUrl: string | null };

/**
 * Request a new verification email.
 *
 * The endpoint answers 200 whether or not the address has an unverified
 * account, so it cannot be used to enumerate registered emails. Success
 * therefore means "the request was accepted" and nothing more — callers must
 * phrase their confirmation conditionally rather than claiming a mail was sent.
 * `dev_verification_url` is populated outside production only.
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
