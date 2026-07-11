import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import jwt from "jsonwebtoken";

export async function GET() {
  const session = await getServerSession(authOptions);
  // Use the provider-namespaced id (e.g. "google:alice@x.com"), not the raw
  // email, so the backend principal can't be spoofed across providers.
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const secret = process.env.BACKEND_JWT_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }
  const token = jwt.sign({ sub: userId }, secret, { algorithm: "HS256", expiresIn: "15m" });
  return NextResponse.json({ token });
}
