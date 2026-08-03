import { devices } from "@playwright/test";
import type { PlaywrightTestConfig } from "@playwright/test";

/**
 * Settings shared by the three Playwright configs, so that a value only one of
 * them needs changed cannot quietly leave the other two behind.
 *
 * Each config still reads as a Playwright config — these are objects to spread,
 * not a framework. What stays in the individual configs is what genuinely
 * differs between the suites: which spec files they select, which port they
 * claim, and how they get a server to talk to.
 */

/**
 * True of all three suites.
 *
 * `timeout`/`expect` are here rather than in devServerSuite because every suite
 * talks to `next dev`, including the Docker one — see the budget note below.
 */
export const base = {
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  use: { trace: "on-first-retry" },

  // The cold-start budget. `next dev` compiles each route the first time it is
  // requested, and an e2e suite is usually the first thing to touch every
  // route, so early assertions are waiting on the compiler rather than on the
  // app. Against a cold machine the six run-detail tests in smoke.spec.ts all
  // failed on `Test timeout of 30000ms exceeded`, each stuck on an expect that
  // had given up after Playwright's default 5s; the immediate re-run passed all
  // fifteen in a third of the time against the same server. A slow assertion is
  // not a failing one, and these ceilings exist to catch a hang, not to hold
  // the compiler to a deadline.
  timeout: 90_000,
  expect: { timeout: 20_000 },
} satisfies PlaywrightTestConfig;

/**
 * The two suites that boot their own `next dev` (main and demo). The Docker
 * suite is excluded deliberately: it runs one long serial test against an
 * already-running compose stack, so it wants neither the parallelism nor the
 * HTML reporter.
 *
 * Workers are capped below Playwright's default of half the CPUs on the theory
 * that parallel cold compiles slow each other down. Measured at roughly a
 * second of total suite time either way, so it is close to free — it is the
 * budget above that actually fixed the flake, not this.
 */
export const devServerSuite = {
  ...base,
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 3,
  reporter: [["html", { open: "never" }]],
} satisfies PlaywrightTestConfig;
