import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";

export const authOptions: NextAuthOptions = {
  // CredentialsProvider requires the JWT session strategy (no DB adapter is
  // configured, so this is already the default — set explicitly for clarity).
  session: { strategy: "jwt" },
  providers: [
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
  secret: process.env.NEXTAUTH_SECRET,
};
