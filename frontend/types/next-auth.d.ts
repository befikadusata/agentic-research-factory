import "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
    };
  }

  interface User {
    id: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    /** Which provider the user signed in with ("google" | "credentials").
     *  Namespaces the backend principal, so the same email on two providers
     *  maps to distinct, non-overlapping identities. */
    provider?: string;
  }
}
