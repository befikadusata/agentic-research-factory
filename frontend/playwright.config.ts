import { defineConfig, devices } from "@playwright/test";

// Its own port rather than Next's default 3000, for the same reason
// playwright.demo.config.ts claims 3100: `reuseExistingServer` cannot tell our
// dev server from anything else already listening, so on a machine where some
// unrelated project owns 3000 the entire suite silently runs against that
// server and every test fails for reasons found nowhere in this repo.
const PORT = 3200;
const APP_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  // demo.spec.ts needs NEXT_PUBLIC_DEMO=1 — it runs from playwright.demo.config.ts.
  testIgnore: ["**/debug*.spec.ts", "**/docker-auth.spec.ts", "**/demo.spec.ts"],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: APP_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npm run dev -- -p ${PORT}`,
    url: APP_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
    env: {
      // A developer's .env.local pins NEXTAUTH_URL to :3000; without this
      // override NextAuth's post-sign-in redirect leaves the server under test.
      NEXTAUTH_URL: APP_URL,
    },
  },
});
