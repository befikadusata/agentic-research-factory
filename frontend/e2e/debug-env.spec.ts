import { test } from "@playwright/test";

test("debug - check server env", async ({ page }) => {
  // Create a temporary API route to check env
  page.on("response", async (res) => {
    if (res.url().includes("/api/debug-env")) {
      const body = await res.json();
      console.log("Server env check:", JSON.stringify(body));
    }
  });

  // Navigate to a page that doesn't require auth (backend-token is excluded from middleware)
  await page.goto("/api/backend-token");
  // Cancel the navigation since we just want to check
});
