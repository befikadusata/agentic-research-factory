import { expect, test } from "@playwright/test";

test("registers, verifies, signs in through Docker, signs out, and signs in again", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const email = `docker-auth-${Date.now()}@example.com`;
  const password = "docker-test-password";

  await page.goto("/");
  await page.getByRole("button", { name: "Register" }).click();
  await page.getByPlaceholder("Name (optional)").fill("Docker Auth Test");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password (min 8 characters)").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("status")).toContainText("verification link");
  const verificationHref = await page.getByRole("link", { name: /Dev only — verify link/i }).getAttribute("href");
  expect(verificationHref).toBeTruthy();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "isn't verified yet" })).toBeVisible();

  await page.goto(verificationHref!);
  await expect(page.getByRole("status")).toContainText("Email verified");
  await page.getByRole("link", { name: "Continue to sign in" }).click();

  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid email or password." })).toBeVisible();

  await page.getByPlaceholder("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent Runs" })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
  expect(browserErrors).toEqual([]);
  await page.waitForLoadState("networkidle");

  const signOutRequest = page.waitForResponse(
    (response) => response.url().includes("/api/auth/signout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign out" }).click();
  await signOutRequest;
  await page.reload();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent Runs" })).toBeVisible();
});
