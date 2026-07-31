import { NextResponse } from "next/server";
import { withAuth } from "next-auth/middleware";

// Read inline rather than importing lib/demo — Next inlines NEXT_PUBLIC_* here
// too, and this keeps the seed data out of the edge bundle.
const IS_DEMO = process.env.NEXT_PUBLIC_DEMO === "1";

/**
 * Demo mode skips the auth gate entirely.
 *
 * Not a weakening of it: `AppShell` still renders the sign-in screen until you
 * click through, so the flow looks identical. The reason to bypass is that
 * `withAuth` decodes the session cookie with `process.env.NEXTAUTH_SECRET`,
 * which it reads directly and which a zero-setup demo hasn't set — it would
 * disagree with the fallback key in `lib/auth.ts` and bounce every signed-in
 * request straight back to the sign-in screen. There is no protected data
 * behind it in demo mode, so there is nothing for the gate to do.
 */
export default IS_DEMO
  ? function demoMiddleware() {
      return NextResponse.next();
    }
  : withAuth({
      pages: { signIn: "/" },
    });

export const config = {
  matcher: [
    "/((?!api/auth|api/backend-token|verify-email|_next/static|_next/image|favicon\\.ico).*)",
  ],
};
