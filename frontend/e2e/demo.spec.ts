import { test, expect, type Page } from "@playwright/test";

/**
 * Demo mode end-to-end — run with `npm run test:e2e:demo`.
 *
 * Deliberately different from smoke.spec.ts in one way: **no route mocks.** The
 * smoke suite fulfils every backend request itself, so it would pass whether or
 * not demo mode existed. Here the backend URL points at a dead port
 * (playwright.demo.config.ts), so any call that escapes to the network fails —
 * which makes "the app is complete from seed data alone" an assertion rather
 * than a claim. `trackBackendCalls` also checks it explicitly.
 */

/** The unreachable address playwright.demo.config.ts hands the app. */
const DEAD_BACKEND = "127.0.0.1:9";

function trackBackendCalls(page: Page): string[] {
  const calls: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes(DEAD_BACKEND)) calls.push(req.url());
  });
  return calls;
}

async function enterDemo(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Take a look around" })).toBeVisible();
  await page.getByRole("button", { name: "Enter the demo" }).click();
  await expect(page.getByRole("heading", { name: "Recent Runs" })).toBeVisible();
}

test.describe("Demo mode", () => {
  test("signs in with one click and never calls a backend", async ({ page }) => {
    const backendCalls = trackBackendCalls(page);

    await enterDemo(page);
    await expect(page.getByRole("note")).toContainText("Demo mode");

    // Walk the whole app, not just the landing page.
    await expect(page.getByText("How does Notion position itself")).toBeVisible();
    await page.getByRole("link", { name: "Monitors" }).click();
    await expect(page.getByText("Northwind Logistics — account watch")).toBeVisible();
    await page.getByRole("link", { name: "New Run", exact: true }).click();
    await expect(page.getByRole("group", { name: "Playbook" })).toBeVisible();
    await page.getByRole("link", { name: "History" }).click();
    await expect(page.getByRole("heading", { name: "Recent Runs" })).toBeVisible();

    expect(backendCalls, "demo mode must not reach the backend").toEqual([]);
  });

  test("shows a completed run with its output, scores, and markdown download", async ({ page }) => {
    await enterDemo(page);
    await page.getByText("How does Notion position itself").click();

    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
    await expect(page.getByText("Competitive Brief — Notion")).toBeVisible();
    // Persisted logs render from the seed, same as a real completed run.
    await expect(page.getByText("Identified 3 differentiation gaps with supporting evidence")).toBeVisible();

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download MD" }).click();
    expect((await download).suggestedFilename()).toBe("report_demo-competitor-brief.md");

    // PDF is rendered server-side, so the demo says so rather than faking one.
    await page.getByRole("button", { name: "Download PDF" }).click();
    // Scoped by text: Next ships an always-present empty route announcer with
    // role="alert", so a bare getByRole("alert") is ambiguous here.
    await expect(
      page.getByRole("alert").filter({ hasText: "PDF export" }),
    ).toContainText("unavailable in demo mode");
  });

  test("runs the full pipeline: streamed logs, approval gate, then output", async ({ page }) => {
    const backendCalls = trackBackendCalls(page);
    await enterDemo(page);

    await page.getByRole("link", { name: "New Run", exact: true }).click();

    // Retry the click until it takes. The playbook cards are React onClick
    // handlers, and Playwright's actionability checks don't know about
    // hydration — against `next dev` compiling this route for the first time,
    // a single click can land on markup that isn't listening yet and is simply
    // lost. aria-pressed is the signal that the state actually changed.
    const playbook = page.getByRole("group", { name: "Playbook" });
    const card = playbook.getByRole("button", { name: /Marketing Competitor Brief/i });
    await expect(async () => {
      await card.click();
      await expect(card).toHaveAttribute("aria-pressed", "true", { timeout: 2_000 });
    }).toPass({ timeout: 30_000 });

    await page.getByPlaceholder("e.g. Notion, Salesforce, HubSpot").fill("Linear");
    await page
      .getByPlaceholder(/Competitive landscape for Notion/i)
      .fill("How is Linear positioned against Jira?");
    await page.getByRole("button", { name: /Start Marketing/i }).click();

    await expect(page).toHaveURL(/\/runs\/demo-run-/, { timeout: 20_000 });

    // Logs arrive over time rather than all at once — this is the scripted
    // stand-in for the SSE stream, so it has to actually stream.
    await expect(page.getByText("Searching the web — 12 candidate sources found")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Synthesized 8 findings")).toBeVisible({ timeout: 20_000 });

    // The human-in-the-loop gate is the point of the demo: it must block.
    const review = page.getByText("Research Complete — Review Before Analysis");
    await expect(review).toBeVisible({ timeout: 20_000 });
    // The gate shows the research artifact, including what the stage refused to
    // carry forward — that self-reporting is the part worth demonstrating.
    await expect(page.getByText("Eight findings survived the confidence filter")).toBeVisible();

    await page.getByPlaceholder(/Focus more on pricing strategy/i).fill("Focus on pricing.");
    await page.getByRole("button", { name: /Approve & Continue to Analysis/i }).click();

    await expect(page.getByText("Reviewer instruction: Focus on pricing.")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText("How is Linear positioned against Jira?").first()).toBeVisible();

    expect(backendCalls, "a scripted run must not reach the backend either").toEqual([]);
  });

  test("keeps a paused run paused when revisited", async ({ page }) => {
    await enterDemo(page);
    await page.getByText("Is now the right time to enter the SMB legal tech market?").click();

    await expect(page.getByText("Research Complete — Review Before Analysis")).toBeVisible();
    await expect(page.getByText("9 funded entrants")).toBeVisible();
  });

  test("surfaces a failed run's real error message", async ({ page }) => {
    await enterDemo(page);
    await page.getByText("Pricing changes across enterprise observability vendors").click();

    await expect(page.getByText("This run failed. Check the agent logs above for details.")).toBeVisible();
    await expect(page.getByText("6 of 8 pages timed out during scraping")).toBeVisible();
  });

  test("scopes runs to the active workspace", async ({ page }) => {
    await enterDemo(page);
    await expect(page.getByText("How does Notion position itself")).toBeVisible();

    await page.getByRole("button", { name: "Acme Research" }).click();
    await page.getByRole("button", { name: "Personal" }).click();

    await expect(page.getByText("Weekly scan: what changed in retrieval-augmented generation")).toBeVisible();
    await expect(page.getByText("How does Notion position itself")).toBeHidden();
  });

  test("waits for an uploaded PDF to finish indexing before it can be used", async ({ page }) => {
    await enterDemo(page);
    await page.getByRole("link", { name: "New Run", exact: true }).click();
    await expect(page.getByRole("group", { name: "Playbook" })).toBeVisible();

    // Retried for the same reason the playbook click above is: react-dropzone's
    // onChange may not be attached yet on a freshly compiled `next dev` route,
    // and a file set into an unlistening input is silently dropped.
    const attached = page.getByText(/market-notes\.pdf/);
    await expect(async () => {
      await page.locator('input[type="file"]').setInputFiles({
        name: "market-notes.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.4 demo fixture"),
      });
      await expect(attached).toBeVisible({ timeout: 3_000 });
    }).toPass({ timeout: 30_000 });

    // Storing the file is not indexing it. Until the chunks exist the run must
    // not be startable — otherwise it retrieves nothing and cites a source it
    // never read.
    await expect(page.getByText("Indexing market-notes.pdf…")).toBeVisible();
    await expect(page.getByRole("button", { name: /Waiting for your PDF/i })).toBeDisabled();

    await expect(page.getByText("chunks indexed")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Start Research" })).toBeEnabled();
  });

  test("offers 'save as monitor' only for runs no monitor already owns", async ({ page }) => {
    await enterDemo(page);

    // Spawned by the Northwind monitor — offering to monitor it again is noise.
    await page.getByText("Prospect dossier for Northwind Logistics").click();
    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Save as monitor/i })).toBeHidden();

    await page.getByRole("link", { name: "History" }).click();
    await page.getByText("How does Notion position itself").click();
    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Save as monitor/i })).toBeVisible();
  });

  test("lists seeded workspace members", async ({ page }) => {
    await enterDemo(page);
    await page.getByRole("button", { name: "Acme Research" }).click();
    await page.getByRole("button", { name: "Manage members" }).click();

    const dialog = page.getByRole("dialog", { name: "Workspace members" });
    await expect(dialog).toContainText("priya@acme.example");
    await expect(dialog).toContainText("sam@acme.example");
  });
});
