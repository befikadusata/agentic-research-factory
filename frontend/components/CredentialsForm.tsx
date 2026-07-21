"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";

type Mode = "login" | "register";

export function CredentialsForm() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [showResend, setShowResend] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function resetMessages() {
    setError(null);
    setNotice(null);
    setDevLink(null);
    setShowResend(false);
  }

  async function handleRegister() {
    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name || null }),
    });
    if (!res.ok) {
      if (res.status === 409) setError("An account with this email already exists.");
      else if (res.status === 422) setError("Password must be at least 8 characters.");
      else setError("Registration failed. Please try again.");
      return;
    }
    const data = await res.json();
    // Account created but unverified — do NOT sign in yet.
    setNotice(`We sent a verification link to ${email}. Click it, then sign in.`);
    if (data.dev_verification_url) setDevLink(data.dev_verification_url);
    setMode("login");
  }

  async function handleLogin() {
    const result = await signIn("credentials", { email, password, redirect: false });
    if (result?.error) {
      if (result.error.includes("EMAIL_NOT_VERIFIED")) {
        setError("Your email isn't verified yet. Check your inbox, or resend the link below.");
        setShowResend(true);
      } else {
        setError("Invalid email or password.");
      }
      return;
    }
    window.location.assign("/");
  }

  async function handleResend() {
    resetMessages();
    setSubmitting(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/auth/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      setNotice(`If an unverified account exists for ${email}, a new link is on its way.`);
      if (data.dev_verification_url) setDevLink(data.dev_verification_url);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    resetMessages();
    setSubmitting(true);
    try {
      if (mode === "register") await handleRegister();
      else await handleLogin();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-3 text-left">
      {mode === "register" && (
        <input
          type="text"
          placeholder="Name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-4 py-2.5 rounded-md bg-surface-2 border border-border-subtle text-content placeholder:text-content-muted focus:outline-none focus:border-primary"
        />
      )}
      <input
        type="email"
        required
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full px-4 py-2.5 rounded-md bg-surface-2 border border-border-subtle text-content placeholder:text-content-muted focus:outline-none focus:border-primary"
      />
      <input
        type="password"
        required
        minLength={mode === "register" ? 8 : undefined}
        placeholder={mode === "register" ? "Password (min 8 characters)" : "Password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full px-4 py-2.5 rounded-md bg-surface-2 border border-border-subtle text-content placeholder:text-content-muted focus:outline-none focus:border-primary"
      />

      {error && (
        <p role="alert" className="text-sm text-feedback-error bg-feedback-error/10 border border-feedback-error/40 rounded-md px-3 py-2">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-sm text-content bg-agent-thinking/10 border border-agent-thinking/40 rounded-md px-3 py-2">
          {notice}
        </p>
      )}
      {devLink && (
        <a
          href={devLink}
          className="block text-xs text-primary hover:text-primary-hover break-all border border-dashed border-border-subtle rounded-md px-3 py-2"
        >
          Dev only — verify link: {devLink}
        </a>
      )}
      {showResend && (
        <button
          type="button"
          onClick={handleResend}
          disabled={submitting}
          className="text-sm text-primary hover:text-primary-hover font-medium disabled:opacity-60"
        >
          Resend verification email
        </button>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-primary hover:bg-primary-hover text-primary-on font-medium px-4 py-2.5 rounded-md transition-colors duration-base disabled:opacity-60"
      >
        {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
      </button>

      <p className="text-sm text-content-secondary text-center">
        {mode === "login" ? "Don't have an account? " : "Already have an account? "}
        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            resetMessages();
          }}
          className="text-primary hover:text-primary-hover font-medium"
        >
          {mode === "login" ? "Register" : "Sign in"}
        </button>
      </p>
    </form>
  );
}
