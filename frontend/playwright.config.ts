import { defineConfig } from "@playwright/test";
import { base, devServerSuite } from "./playwright.base";

// Its own port rather than Next's default 3000, for the same reason
// playwright.demo.config.ts claims 3100: an unrelated project owning 3000 is
// entirely normal, and Playwright cannot tell that server from ours.
const PORT = 3200;
const APP_URL = `http://localhost:${PORT}`;

export default defineConfig({
  ...devServerSuite,
  // demo.spec.ts needs NEXT_PUBLIC_DEMO=1 — it runs from playwright.demo.config.ts.
  testIgnore: ["**/debug*.spec.ts", "**/docker-auth.spec.ts", "**/demo.spec.ts"],
  use: {
    ...base.use,
    baseURL: APP_URL,
  },
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
