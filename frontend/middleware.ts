import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: { signIn: "/" },
});

export const config = {
  matcher: [
    "/((?!api/auth|api/backend-token|_next/static|_next/image|favicon\\.ico).*)",
  ],
};
