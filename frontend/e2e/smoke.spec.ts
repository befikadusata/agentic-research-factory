import { test, expect } from "@playwright/test";
import { EncryptJWT } from "jose";
import hkdf from "@panva/hkdf";
import crypto from "crypto";

const TEST_AUTH_SECRET = "test-secret-at-least-32-chars-long-for-e2e";

async function createSessionCookie(page: import("@playwright/test").Page) {
  const encryptionSecret = await hkdf(
    "sha256",
    TEST_AUTH_SECRET,
    "",
    "NextAuth.js Generated Encryption Key",
    32,
  );

  const token = await new EncryptJWT({
    sub: "test-user-id",
    name: "Test User",
    email: "test@example.com",
    picture: null,
  })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + 30 * 24 * 60 * 60)
    .setJti(crypto.randomUUID())
    .encrypt(encryptionSecret);

  await page.context().addCookies([
    {
      name: "next-auth.session-token",
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

function mockAuthenticatedSession(page: import("@playwright/test").Page) {
  return page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "test-user-id", name: "Test User", email: "test@example.com" },
        expires: "2099-01-01T00:00:00.000Z",
      }),
    });
  });
}

function mockBackendToken(page: import("@playwright/test").Page) {
  return page.route("**/api/backend-token", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ token: "test-backend-token" }),
    });
  });
}

test.describe("Core Flow Smoke Tests", () => {
  test("adapts the application shell across mobile, tablet, and desktop", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/runs", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await createSessionCookie(page);

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/new");

    await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    await expect(page.locator("aside")).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);

    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(page.getByRole("dialog", { name: "Application navigation" })).toBeVisible();
    await expect(page.getByRole("link", { name: "History" })).toBeVisible();
    await page.getByRole("button", { name: "Close navigation" }).click();
    await expect(page.getByRole("dialog", { name: "Application navigation" })).not.toBeVisible();

    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 667, height: 375 });
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    await expect(page.locator("aside")).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(667);

    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    await expect(page.locator("aside")).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(768);

    await page.setViewportSize({ width: 1440, height: 1000 });
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeHidden();
    await expect(page.locator("aside")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);
  });

  test("exposes keyboard focus, current navigation, selector state, and errors", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/verticals", async (route) => {
      await route.abort();
    });
    await createSessionCookie(page);
    await page.goto("/new");

    await page.keyboard.press("Tab");
    const skipLink = page.getByRole("link", { name: "Skip to main content" });
    await expect(skipLink).toBeFocused();
    expect(await skipLink.evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();

    await expect(page.getByRole("link", { name: "New Run" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("link", { name: "History" })).not.toHaveAttribute("aria-current");

    const generalFormat = page.getByRole("button", { name: /Full Report/i });
    const summaryFormat = page.getByRole("button", { name: /Executive Summary/i });
    await expect(generalFormat).toHaveAttribute("aria-pressed", "true");
    await summaryFormat.click();
    await expect(summaryFormat).toHaveAttribute("aria-pressed", "true");
    await expect(generalFormat).toHaveAttribute("aria-pressed", "false");

    const playbook = page.getByRole("group", { name: "Playbook" });
    await expect(playbook.locator("svg")).toHaveCount(3);
    await expect(playbook).not.toContainText(/[🎯📊🚀]/);
    const marketingPlaybook = playbook.getByRole("button", { name: /Marketing Competitor Brief/i });
    await marketingPlaybook.click();
    await expect(marketingPlaybook).toHaveAttribute("aria-pressed", "true");
    await page.getByPlaceholder(/Competitive landscape for Notion/i).fill("Competitive landscape");
    await page.getByRole("button", { name: /Start Marketing/i }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Competitor Name" })).toBeVisible();
  });

  test("recovers when the runs list fails to load", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/workspaces", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: "workspace-1", name: "Research Team", owner_id: "test-user-id", role: "admin" }]),
      });
    });

    let attempts = 0;
    await page.route("**/runs?**", async (route) => {
      attempts += 1;
      if (attempts === 1) {
        await route.fulfill({ status: 503, contentType: "text/plain", body: "Temporary service outage" });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          id: "recovered-run",
          topic: "Recovered market research",
          format: "report",
          status: "complete",
          workspace_id: "workspace-1",
          created_at: "2026-01-01T00:00:00Z",
        }]),
      });
    });

    await createSessionCookie(page);
    await page.goto("/");

    const loadError = page.getByRole("alert").filter({ hasText: "Runs couldn’t be loaded" });
    await expect(loadError).toContainText("Runs couldn’t be loaded");
    await expect(loadError).toContainText("Temporary service outage");
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(page.getByText("Recovered market research")).toBeVisible();
  });

  test("explains monitor deletion before confirming it", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/workspaces", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await page.route("**/monitors/monitor-1/runs", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await page.route("**/monitors/monitor-1", async (route) => {
      if (route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "monitor-1",
          user_id: "test-user-id",
          workspace_id: null,
          name: "Competitor watch",
          topic: "Track competitor pricing",
          format: "report",
          interval_minutes: 1440,
          enabled: true,
          next_run_at: "2026-07-22T00:00:00Z",
          last_run_id: null,
          last_run_at: null,
          notify_channel: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }),
      });
    });

    await createSessionCookie(page);
    await page.goto("/monitors/monitor-1");
    await page.getByRole("button", { name: "Delete" }).click();

    const dialog = page.getByRole("dialog", { name: "Delete this monitor?" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("past research runs will remain available");
    await dialog.getByRole("button", { name: "Keep monitor" }).click();
    await expect(dialog).not.toBeVisible();
  });

  test("keeps workspace member management accessible during loading and removal", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/workspaces", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: "workspace-1", name: "Research Team", owner_id: "credentials:test@example.com", role: "admin" }]),
      });
    });
    await page.route("**/runs?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });

    let releaseMembers: (() => void) | undefined;
    const membersReady = new Promise<void>((resolve) => { releaseMembers = resolve; });
    await page.route("**/workspaces/workspace-1/members", async (route) => {
      await membersReady;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { user_id: "credentials:test@example.com", role: "admin" },
          { user_id: "google:teammate@example.com", role: "viewer" },
        ]),
      });
    });

    await createSessionCookie(page);
    await page.goto("/");

    const workspaceButton = page.getByRole("button", { name: "Research Team" });
    await workspaceButton.click();
    await page.getByRole("button", { name: "Manage members" }).click();

    const membersDialog = page.getByRole("dialog", { name: "Workspace members" });
    await expect(membersDialog).toBeVisible();
    await expect(membersDialog.getByRole("status", { name: "Loading workspace members" })).toBeVisible();
    releaseMembers?.();

    await expect(membersDialog.getByLabel("Email address")).toBeVisible();
    await expect(membersDialog.getByLabel("Sign-in method")).toBeVisible();
    await expect(membersDialog.getByLabel("Workspace role")).toBeVisible();

    await membersDialog.getByRole("button", { name: "Remove teammate@example.com" }).click();
    const confirmation = page.getByRole("dialog", { name: "Remove this member?" });
    await expect(confirmation).toContainText("teammate@example.com will lose access to Research Team");
    await confirmation.getByRole("button", { name: "Keep member" }).click();
    await expect(confirmation).not.toBeVisible();

    await page.keyboard.press("Escape");
    await expect(membersDialog).not.toBeVisible();
    await expect(workspaceButton).toBeFocused();
  });

  test("announces email verification progress and provides clear outcomes", async ({ page }) => {
    let releaseVerification: (() => void) | undefined;
    const verificationReady = new Promise<void>((resolve) => { releaseVerification = resolve; });
    await page.route("**/auth/verify-email", async (route) => {
      await verificationReady;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ email: "verified@example.com" }),
      });
    });

    await page.goto("/verify-email?token=valid-token");

    const verificationProgress = page.getByRole("status").filter({ hasText: "Verifying your email" });
    await expect(verificationProgress).toBeVisible();
    await expect(verificationProgress).toContainText("This should only take a moment");
    releaseVerification?.();

    const verificationComplete = page.getByRole("status").filter({ hasText: "Email verified" });
    await expect(verificationComplete).toContainText("verified@example.com is confirmed");
    await expect(verificationComplete.getByRole("link", { name: "Continue to sign in" })).toHaveAttribute("href", "/");

    await page.goto("/verify-email");
    const verificationError = page.getByRole("alert").filter({ hasText: "Verification failed" });
    await expect(verificationError).toContainText("invalid or has expired");
    await expect(verificationError.getByRole("link", { name: "Back to sign in" })).toHaveAttribute("href", "/");
  });

  test("offers a new verification link from the expired-link dead end", async ({ page }) => {
    let resendPayload: Record<string, unknown> | null = null;
    await page.route("**/auth/resend-verification", async (route) => {
      resendPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", dev_verification_url: "http://localhost:3200/verify-email?token=fresh" }),
      });
    });

    // No token at all, which is the same dead end an expired link reaches: the
    // page cannot know the address, so the form has to ask for it.
    await page.goto("/verify-email");
    await expect(page.getByRole("alert").filter({ hasText: "Verification failed" })).toBeVisible();

    await page.getByLabel("Send a new link").fill("unverified@example.com");
    await page.getByRole("button", { name: "Resend verification email" }).click();

    // Non-committal by design — the endpoint answers identically for an address
    // with no account, and this copy must not leak what it withholds.
    await expect(page.getByRole("status")).toContainText(
      "If an unverified account exists for unverified@example.com, a new link is on its way.",
    );
    await expect(page.getByRole("link", { name: /Dev only/ })).toBeVisible();
    expect(resendPayload).toEqual({ email: "unverified@example.com" });
  });

  test("surfaces a failed resend instead of claiming the mail was sent", async ({ page }) => {
    await page.route("**/auth/resend-verification", (route) => route.fulfill({ status: 500, body: "" }));

    await page.goto("/verify-email");
    await page.getByLabel("Send a new link").fill("unverified@example.com");
    await page.getByRole("button", { name: "Resend verification email" }).click();

    await expect(page.getByRole("alert").filter({ hasText: "couldn’t send a new link" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
  });

  test("creates run with vertical payload and redirects to run detail", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);

    let createPayload: Record<string, unknown> | null = null;

    await page.route("**/runs", async (route) => {
      if (route.request().method() === "POST") {
        createPayload = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({ id: "run-123" }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });

    await page.route("**/runs/run-123", async (route) => {
      if (route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "run-123",
          topic: "How does Notion position itself?",
          format: "report",
          status: "writing",
          workspace_id: null,
          vertical: "marketing_competitor_briefs",
          created_at: "2026-01-01T00:00:00Z",
          logs: [],
          research_output: "Draft research",
          final_output: null,
        }),
      });
    });

    await page.route("**/runs/run-123/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: 'retry: 10000\ndata: {"type":"ping","data":{}}\n\n',
      });
    });

    await createSessionCookie(page);
    await page.goto("/new");
    await page.getByText("Marketing Competitor Brief").click();
    await page.getByPlaceholder("e.g. Notion, Salesforce, HubSpot").fill("Notion");
    await page.getByPlaceholder("e.g. AI writing assistant for startups").fill("AcmeDocs");
    await page.getByPlaceholder("e.g. Competitive landscape for Notion in project management, 2025").fill("How does Notion position itself?");
    await page.getByRole("button", { name: /Start Marketing/i }).click();

    await expect(page).toHaveURL(/\/runs\/run-123$/, { timeout: 20_000 });
    expect(createPayload).not.toBeNull();
    expect(createPayload!.vertical).toBe("marketing_competitor_briefs");
    expect(createPayload!.topic).toBe("How does Notion position itself?");
    expect(createPayload!.vertical_inputs).toEqual({
      competitor_name: "Notion",
      our_product: "AcmeDocs",
    });
  });

  test("keeps an early playbook click consistent while verticals refresh", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    let releaseVerticals: (() => void) | undefined;
    const verticalsReady = new Promise<void>((resolve) => { releaseVerticals = resolve; });
    let createPayload: Record<string, unknown> | null = null;

    await page.route("**/verticals", async (route) => {
      await verticalsReady;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          key: "marketing_competitor_briefs",
          display_name: "Refreshed Competitor Brief",
          description: "Backend-authoritative definition",
          default_format: "summary",
          input_schema: {
            competitor_name: { label: "Current Competitor", required: true, placeholder: "Updated competitor", type: "text" },
          },
        }]),
      });
    });
    await page.route("**/runs", async (route) => {
      createPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "delayed-run" }) });
    });
    await page.route("**/runs/delayed-run", async (route) => {
      if (route.request().isNavigationRequest()) return route.continue();
      await route.fulfill({ status: 404, body: "not needed" });
    });

    await createSessionCookie(page);
    await page.goto("/new");
    const playbookGroup = page.getByRole("group", { name: "Playbook" });
    const initialCard = playbookGroup.getByRole("button", { name: /Marketing Competitor Brief/i });
    await initialCard.click();
    await expect(initialCard).toHaveAttribute("aria-pressed", "true");
    releaseVerticals?.();

    const refreshedCard = playbookGroup.getByRole("button", { name: /Refreshed Competitor Brief/i });
    await expect(refreshedCard).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: /Executive Summary/i })).toHaveAttribute("aria-pressed", "true");
    await page.getByPlaceholder("Updated competitor").fill("Notion");
    await refreshedCard.click();
    await expect(page.getByPlaceholder("Updated competitor")).toHaveValue("Notion");
    await page.getByPlaceholder(/Competitive landscape for Notion/i).fill("Current Notion positioning");
    await page.getByRole("button", { name: /Start Refreshed/i }).click();
    await expect(page).toHaveURL(/\/runs\/delayed-run$/, { timeout: 20_000 });
    expect(createPayload).toMatchObject({
      vertical: "marketing_competitor_briefs",
      format: "summary",
      vertical_inputs: { competitor_name: "Notion" },
    });
  });

  test("revisits and reloads a completed run with persisted logs", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/runs/revisited-run", async (route) => {
      if (route.request().isNavigationRequest()) return route.continue();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "revisited-run",
          topic: "Persisted report",
          format: "report",
          status: "complete",
          workspace_id: null,
          vertical: null,
          created_at: "2026-07-21T10:00:00Z",
          updated_at: "2026-07-21T10:05:00Z",
          logs: [
            { agent: "system", message: "Status changed to researching", ts: "2026-07-21T10:00:01Z" },
            { agent: "Researcher", message: "Collected current evidence", ts: "2026-07-21T10:01:00Z" },
            { agent: "error", message: "Recovered non-fatal tool error", ts: "2026-07-21T10:02:00Z" },
          ],
          research_output: "Research body",
          analysis_output: "Analysis body",
          final_output: "# Persisted Final Output\n\nStill available after refresh.",
          error_message: null,
        }),
      });
    });
    await page.route("**/runs/revisited-run/stream", async (route) => {
      await route.fulfill({ status: 200, headers: { "content-type": "text/event-stream" }, body: "" });
    });

    await createSessionCookie(page);
    await page.goto("/runs/revisited-run");
    await expect(page.getByText("Persisted Final Output")).toBeVisible();
    await expect(page.getByText("Collected current evidence")).toBeVisible();
    await page.getByRole("button", { name: "Errors" }).click();
    await expect(page.getByText("Recovered non-fatal tool error")).toBeVisible();
    await expect(page.getByText("Collected current evidence")).not.toBeVisible();

    await page.reload();
    await expect(page.getByText("Persisted Final Output")).toBeVisible();
    await expect(page.getByText("Collected current evidence")).toBeVisible();
  });

  test("labels runs with a playbook only the backend knows about", async ({ page }) => {
    // The bundled VERTICALS list is a fallback, not the authority. /new always
    // asked the backend, but the run list and run detail read the bundle — so a
    // playbook added server-side produced runs you could start and then never
    // see identified anywhere afterwards.
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);
    await page.route("**/verticals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          key: "regulatory_watch",
          display_name: "Regulatory Watch",
          description: "Defined on the server only",
          default_format: "report",
          input_schema: {},
        }]),
      });
    });
    await page.route("**/workspaces", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: "workspace-1", name: "Research Team", owner_id: "test-user-id", role: "admin" }]),
      });
    });
    await page.route("**/runs?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{
          id: "novel-playbook-run",
          topic: "EU AI Act obligations",
          format: "report",
          status: "complete",
          workspace_id: "workspace-1",
          vertical: "regulatory_watch",
          created_at: "2026-01-01T00:00:00Z",
        }]),
      });
    });
    await page.route("**/runs/novel-playbook-run", async (route) => {
      if (route.request().isNavigationRequest()) return route.continue();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "novel-playbook-run",
          topic: "EU AI Act obligations",
          format: "report",
          status: "complete",
          workspace_id: "workspace-1",
          vertical: "regulatory_watch",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:05:00Z",
          logs: [],
          final_output: "# Obligations",
        }),
      });
    });
    await page.route("**/runs/novel-playbook-run/stream", async (route) => {
      await route.fulfill({ status: 200, headers: { "content-type": "text/event-stream" }, body: "" });
    });

    await createSessionCookie(page);
    await page.goto("/");
    // The list badge — the surface that used to render nothing at all here.
    await expect(page.getByText("Regulatory Watch")).toBeVisible();

    await page.getByText("EU AI Act obligations").click();
    await expect(page.getByText("Regulatory Watch")).toBeVisible();
    // The badge carries an icon, and an unknown key used to resolve to
    // `undefined` — which React rejects as an element type, taking the page
    // down rather than merely looking generic.
    await expect(page.getByText("Obligations")).toBeVisible();
  });

  test("shows HITL modal and approves with optional instruction", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);

    let approvePayload: Record<string, unknown> | null = null;

    await page.route("**/runs/hitl-run", async (route) => {
      if (route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "hitl-run",
          topic: "Competitive landscape",
          format: "report",
          status: "awaiting_research_approval",
          workspace_id: null,
          vertical: null,
          created_at: "2026-01-01T00:00:00Z",
          logs: [],
          research_output: "## Research summary\n\n- Finding 1",
          final_output: null,
        }),
      });
    });

    await page.route("**/runs/hitl-run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: 'retry: 10000\ndata: {"type":"ping","data":{}}\n\n',
      });
    });

    await page.route("**/runs/hitl-run/approve", async (route) => {
      approvePayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "resumed" }),
      });
    });

    await createSessionCookie(page);
    await page.goto("/runs/hitl-run");
    await expect(page.getByText("Research Complete — Review Before Analysis")).toBeVisible();
    await page.getByRole("button", { name: "Review later" }).click();
    await expect(page.getByText("The pipeline is paused safely at this checkpoint.")).toBeVisible();
    await page.getByRole("button", { name: "Open review" }).click();
    await expect(page.getByText("Research Complete — Review Before Analysis")).toBeVisible();
    await page.getByPlaceholder(/Focus more on pricing strategy/i).fill("Focus on pricing and enterprise segment.");
    await page.getByRole("button", { name: /Approve & Continue to Analysis/i }).click();
    await page.waitForResponse((res) => res.url().includes("/approve") && res.status() === 200);

    await expect(page.getByText("Research Complete — Review Before Analysis")).not.toBeVisible();
    expect(approvePayload).not.toBeNull();
    expect(approvePayload!.instruction).toBe("Focus on pricing and enterprise segment.");
  });

  test("renders output panel when stream sends complete event", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);

    async function mockCompleteRunFirst(route: import("@playwright/test").Route) {
      if (route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "complete-run",
          topic: "AI market brief",
          format: "summary",
          status: "writing",
          workspace_id: null,
          vertical: null,
          created_at: "2026-01-01T00:00:00Z",
          logs: [],
          research_output: "Research body",
          final_output: null,
        }),
      });
      await page.unroute("**/runs/complete-run", mockCompleteRunFirst);
      await page.route("**/runs/complete-run", async (route) => {
        if (route.request().isNavigationRequest()) {
          await route.continue();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "complete-run",
            topic: "AI market brief",
            format: "summary",
            status: "complete",
            workspace_id: null,
            vertical: null,
            created_at: "2026-01-01T00:00:00Z",
            logs: [],
            research_output: "Research body",
            final_output: "# Final Brief\n\nDone.",
          }),
        });
      });
    }

    await page.route("**/runs/complete-run", mockCompleteRunFirst);

    await page.route("**/runs/complete-run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: 'retry: 10000\ndata: {"type":"complete","data":{"final_output":"# Final Brief\\n\\nDone."}}\n\n',
      });
    });

    await createSessionCookie(page);
    await page.goto("/runs/complete-run");
    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
    await expect(page.getByText("Final Brief")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download PDF" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Download MD" })).toBeVisible();
  });

  test("shows the real backend error message when a run fails during a live session", async ({ page }) => {
    // §10.1 regression: the "error" stream event used to only flip status to
    // "failed" without storing parsed.data.message, so the banner fell back to
    // run.error_message — null for a run that fails after the page already loaded.
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);

    await page.route("**/runs/failing-run", async (route) => {
      if (route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "failing-run",
          topic: "AI market brief",
          format: "summary",
          status: "researching",
          workspace_id: null,
          vertical: null,
          created_at: "2026-01-01T00:00:00Z",
          logs: [],
          research_output: null,
          final_output: null,
          error_message: null,
        }),
      });
    });

    await page.route("**/runs/failing-run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: 'retry: 10000\ndata: {"type":"error","data":{"message":"Run failed: rate limit exceeded"}}\n\n',
      });
    });

    await createSessionCookie(page);
    await page.goto("/runs/failing-run");

    await expect(page.getByText("This run failed. Check the agent logs above for details.")).toBeVisible();
    await expect(page.getByText("Run failed: rate limit exceeded")).toBeVisible();
    await expect(page.getByRole("link", { name: "Start a new run" })).toHaveAttribute("href", "/new");
    await expect(page.getByRole("link", { name: "Back to runs" })).toHaveAttribute("href", "/");
  });
});
