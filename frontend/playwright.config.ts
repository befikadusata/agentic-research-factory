import { defineConfig, devices } from "@playwright/test";

// Its own port rather than Next's default 3000, for the same reason
// playwright.demo.config.ts claims 3100: an unrelated project owning 3000 is
// entirely normal, and Playwright cannot tell that server from ours.
const PORT = 3200;
const APP_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  // demo.spec.ts needs NEXT_PUBLIC_DEMO=1 — it runs from playwright.demo.config.ts.
  testIgnore: ["**/debug*.spec.ts", "**/docker-auth.spec.ts", "**/demo.spec.ts"],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // Same cold-start budget as playwright.demo.config.ts, for the same reason.
  // `next dev` compiles each route the first time it is requested, and this
  // suite is the first thing to touch every route. On a cold machine the six
  // run-detail tests blew the default 5s expect timeout and failed as a group,
  // where the same suite against a warm server passed in a third of the time —
  // a slow assertion, not a failing one. The timeouts below are what fixes
  // that; the worker cap is a hedge, matching the demo config, on the theory
  // that parallel cold compiles slow each other down. Measured at ~1s of total
  // suite time versus the default (half the CPUs), so it is close to free.
  workers: process.env.CI ? 1 : 3,
  timeout: 90_000,
  expect: { timeout: 20_000 },
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
    // Never reuse, matching playwright.demo.config.ts. `reuseExistingServer`
    // decides by asking whether *something* answers on the port, which is not
    // the same question as whether it is this app — when it guesses wrong the
    // whole suite runs against a stranger and fails with symptoms that appear
    // nowhere in this repo. Booting our own server costs a few seconds and
    // makes that failure impossible rather than merely rarer.
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      // A developer's .env.local pins NEXTAUTH_URL to :3000; without this
      // override NextAuth's post-sign-in redirect leaves the server under test.
      NEXTAUTH_URL: APP_URL,
    },
  },
});
