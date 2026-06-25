import { test, expect } from "@playwright/test";
import { EncryptJWT } from "jose";
import hkdf from "@panva/hkdf";
import crypto from "crypto";

const TEST_AUTH_SECRET = "test-secret-at-least-32-chars-long-for-e2e";

async function createSessionCookie(page) {
  const encryptionSecret = await hkdf("sha256", TEST_AUTH_SECRET, "", "NextAuth.js Generated Encryption Key", 32);
  const token = await new EncryptJWT({
    sub: "test-user-id", name: "Test User", email: "test@example.com", picture: null,
  })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + 30 * 24 * 60 * 60)
    .setJti(crypto.randomUUID())
    .encrypt(encryptionSecret);
  await page.context().addCookies([
    { name: "next-auth.session-token", value: token, domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax" },
  ]);
}

test("debug - check /new page", async ({ page }) => {
  page.on("console", msg => console.log("PAGE LOG:", msg.type(), msg.text()));
  page.on("pageerror", err => console.log("PAGE ERROR:", err.message));

  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { name: "Test User", email: "test@example.com" }, expires: "2099-01-01T00:00:00.000Z" }) });
  });
  await page.route("**/api/backend-token", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ token: "test-backend-token" }) });
  });

  await createSessionCookie(page);
  console.log("Cookies before navigation:", await page.context().cookies());

  const response = await page.goto("/new");
  console.log("Navigation response:", response?.status(), response?.url());
  console.log("Current URL:", page.url());
  console.log("Cookies after navigation:", await page.context().cookies());

  const content = await page.textContent("body");
  console.log("Page title/content snippet:", content?.substring(0, 500));

  await page.screenshot({ path: "/tmp/debug-new-page.png", fullPage: true });
});
