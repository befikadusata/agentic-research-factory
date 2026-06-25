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

    await expect(page).toHaveURL(/\/runs\/run-123$/);
    expect(createPayload).not.toBeNull();
    expect(createPayload?.vertical).toBe("marketing_competitor_briefs");
    expect(createPayload?.topic).toBe("How does Notion position itself?");
    expect(createPayload?.vertical_inputs).toEqual({
      competitor_name: "Notion",
      our_product: "AcmeDocs",
    });
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
    await page.getByPlaceholder(/Focus more on pricing strategy/i).fill("Focus on pricing and enterprise segment.");
    await page.getByRole("button", { name: /Approve & Continue to Analysis/i }).click();
    await page.waitForResponse((res) => res.url().includes("/approve") && res.status() === 200);

    await expect(page.getByText("Research Complete — Review Before Analysis")).not.toBeVisible();
    expect(approvePayload).not.toBeNull();
    expect(approvePayload?.instruction).toBe("Focus on pricing and enterprise segment.");
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
    await expect(page.getByRole("link", { name: "Download PDF" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download MD" })).toBeVisible();
  });
});
