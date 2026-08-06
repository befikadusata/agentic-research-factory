"use client";

import { useState } from "react";
import { resendVerification } from "@/lib/verification";

/**
 * An email field and a submit that request a fresh verification link.
 *
 * It carries its own email input rather than taking one as a prop: the screen
 * that needs it most reached an expired link, whose token the server just
 * refused to decode, so no address is available.
 */
export function ResendVerification() {
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setDevLink(null);
    setError(null);
    setSubmitting(true);
    try {
      const { devVerificationUrl } = await resendVerification(email);
      // Conditional by design — see resendVerification. Saying "we sent it"
      // would turn this form into a way to test which emails have accounts.
      setNotice(`If an unverified account exists for ${email}, a new link is on its way.`);
      setDevLink(devVerificationUrl);
    } catch {
      setError("We couldn’t send a new link just now. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 border-t border-border-subtle pt-6 text-left">
      <label htmlFor="resend-email" className="block text-sm font-medium text-content">
        Send a new link
      </label>
      <p className="mt-1 text-sm leading-6 text-content-secondary">
        Enter the email you signed up with and we’ll send a fresh verification link.
      </p>
      <input
        id="resend-email"
        type="email"
        required
        autoComplete="email"
        placeholder="you@company.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mt-3 w-full min-h-11 rounded-md border border-border-subtle bg-surface-2 px-4 py-2.5 text-content placeholder:text-content-muted focus:border-primary focus:outline-none"
      />
      <button
        type="submit"
        disabled={submitting}
        className="mt-3 w-full min-h-11 rounded-md bg-primary px-4 py-2.5 font-medium text-primary-on transition-colors duration-base hover:bg-primary-hover disabled:opacity-60"
      >
        {submitting ? "Sending…" : "Resend verification email"}
      </button>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-md border border-feedback-error/40 bg-feedback-error/10 px-3 py-2 text-sm text-feedback-error"
        >
          {error}
        </p>
      )}
      {notice && (
        <p
          role="status"
          className="mt-3 rounded-md border border-agent-thinking/40 bg-agent-thinking/10 px-3 py-2 text-sm text-content"
        >
          {notice}
        </p>
      )}
      {devLink && (
        <a
          href={devLink}
          className="mt-3 block break-all rounded-md border border-dashed border-border-subtle px-3 py-2 text-xs text-primary hover:text-primary-hover"
        >
          Dev only — verify link: {devLink}
        </a>
      )}
    </form>
  );
}
