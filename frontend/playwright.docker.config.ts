import { defineConfig } from "@playwright/test";
import { base } from "./playwright.base";

// Runs against an already-running compose stack rather than booting a server,
// so there is no webServer here and the URL comes from the environment. It
// takes `base` but not `devServerSuite`: one long serial test wants neither
// parallelism nor the HTML reporter. The cold-start budget in `base` does
// apply — the compose frontend runs `next dev` too, and this single test walks
// register -> verify -> sign in -> sign out -> sign in, so its whole route
// sequence is compiled on demand inside one test's timeout.
export default defineConfig({
  ...base,
  testMatch: "docker-auth.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    ...base.use,
    baseURL: process.env.DOCKER_FRONTEND_URL ?? "http://localhost:3000",
  },
});
