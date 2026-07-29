import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";
import { IS_DEMO, DEMO_EMAIL, DEMO_NAME } from "./demo";

/**
 * One-click sign-in for demo mode, registered only when NEXT_PUBLIC_DEMO=1.
 *
 * It authorizes unconditionally, which is safe here for a structural reason
 * rather than a policy one: in demo mode `lib/api.ts` never calls the backend at
 * all, so the session this mints can only ever reach the seed data in
 * `lib/demo.ts`. There is no real account, no real database, and no credential
 * to guess. Outside demo mode this provider does not exist, so it cannot be
 * reached by posting to /api/auth/callback/demo either.
 */
const demoProvider = CredentialsProvider({
  id: "demo",
  name: "Demo",
  credentials: {},
  async authorize() {
    return { id: DEMO_EMAIL, email: DEMO_EMAIL, name: DEMO_NAME };
  },
});

export const authOptions: NextAuthOptions = {
  // CredentialsProvider requires the JWT session strategy (no DB adapter is
  // configured, so this is already the default — set explicitly for clarity).
  session: { strategy: "jwt" },
  providers: [
    ...(IS_DEMO ? [demoProvider] : []),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    CredentialsProvider({
      id: "credentials",
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        const backendUrl =
          process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL;
        if (!backendUrl) throw new Error("BACKEND_URL_NOT_CONFIGURED");
        const res = await fetch(`${backendUrl}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: credentials.email, password: credentials.password }),
        });
        // 403 = correct password but unverified email. Throw a distinct code so
        // the form can prompt to verify/resend instead of "invalid credentials".
        if (res.status === 403) throw new Error("EMAIL_NOT_VERIFIED");
        if (!res.ok) return null; // 401 → generic CredentialsSignin
        const user = await res.json();
        // id is the email so it matches the Google path (email is the app-wide principal).
        return { id: user.email, email: user.email, name: user.name ?? user.email };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // `account` is only present on the initial sign-in; persist the provider
      // on the token so it survives subsequent requests.
      if (account) {
        token.provider = account.provider;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user?.email) {
        // Namespace the principal by provider so a credentials account and a
        // Google account with the SAME email are distinct identities and can
        // never see each other's data. Lowercased to match backend normalization.
        const provider = token.provider ?? "credentials";
        session.user.id = `${provider}:${session.user.email.toLowerCase()}`;
      }
      return session;
    },
  },
  // Demo mode falls back to a fixed throwaway key so `npm run demo` needs no
  // .env.local at all. It only ever signs sessions for the demo user, and those
  // sessions can only reach the in-memory seed data — there is nothing behind
  // them to protect. Any real deployment sets NEXTAUTH_SECRET and this fallback
  // is never reached, because IS_DEMO is false.
  secret: process.env.NEXTAUTH_SECRET ?? (IS_DEMO ? "demo-mode-session-key-not-a-secret" : undefined),
};
