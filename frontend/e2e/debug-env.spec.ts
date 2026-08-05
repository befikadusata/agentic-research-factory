import { test } from "@playwright/test";

test("debug - check server env", async ({ page }) => {
  // Log the body of any /api/debug-env response the page happens to make.
  page.on("response", async (res) => {
    if (res.url().includes("/api/debug-env")) {
      const body = await res.json();
      console.log("Server env check:", JSON.stringify(body));
    }
  });

  // backend-token is excluded from the middleware, so it loads without auth.
  await page.goto("/api/backend-token");
});
