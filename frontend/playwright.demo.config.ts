import { defineConfig } from "@playwright/test";
import { base, devServerSuite } from "./playwright.base";

/**
 * Demo-mode e2e, run separately from the main suite (`npm run test:e2e:demo`).
 *
 * A separate config rather than a second project in playwright.config.ts,
 * because both would need their own `next dev` and two dev servers in one
 * project directory fight over `.next`. Running them as separate invocations
 * sidesteps that, and matches how playwright.docker.config.ts already works.
 *
 * The important property of this suite: **it registers no route mocks at all.**
 * The main smoke suite fulfils every backend request itself, so it would pass
 * even if demo mode did nothing. Here, anything that reaches the network gets a
 * connection error, which is exactly the assertion — the app has to be complete
 * from seed data alone.
 */
// Its own port, so this suite can run next to the main one (and next to whatever
// else happens to own 3000) without either config having to be adjusted.
const DEMO_PORT = 3100;
const DEMO_URL = `http://localhost:${DEMO_PORT}`;

export default defineConfig({
  ...devServerSuite,
  testMatch: "demo.spec.ts",
  use: {
    ...base.use,
    baseURL: DEMO_URL,
  },
  webServer: {
    command: `npm run demo -- -p ${DEMO_PORT}`,
    url: DEMO_URL,
    // Never reuse: a reused server was started without the env below, so the
    // dead-backend guarantee these tests rely on wouldn't hold.
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      // Belt and braces with the npm script, so the config is self-contained.
      NEXT_PUBLIC_DEMO: "1",
      // NextAuth builds its post-sign-in redirect from this, and a developer's
      // .env.local pins it to :3000 — without the override, clicking into the
      // demo would bounce off this server onto whatever owns that port.
      NEXTAUTH_URL: DEMO_URL,
      // Deliberately pointed at a port nothing listens on. If a demo build ever
      // regresses into making a real backend call, it fails fast here instead of
      // quietly succeeding against a developer's running stack.
      NEXT_PUBLIC_BACKEND_URL: "http://127.0.0.1:9",
    },
  },
});
