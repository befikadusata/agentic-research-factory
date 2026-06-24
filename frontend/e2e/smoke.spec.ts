import { test, expect } from "@playwright/test";

function mockAuthenticatedSession(page: import("@playwright/test").Page) {
  return page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { name: "Test User", email: "test@example.com" },
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
      await route.continue();
    });

    await page.route("**/runs/run-123", async (route) => {
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
        body: 'data: {"type":"ping","data":{}}\n\n',
      });
    });

    await page.goto("/new");
    await page.getByText("Marketing Competitor Brief").click();
    await page.getByLabel(/Competitor Name/i).fill("Notion");
    await page.getByLabel(/Your Product/i).fill("AcmeDocs");
    await page.getByRole("textbox", { name: /Research Topic/i }).fill("How does Notion position itself?");
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
        body: 'data: {"type":"ping","data":{}}\n\n',
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

    await page.goto("/runs/hitl-run");
    await expect(page.getByText(/Research Complete/i)).toBeVisible();
    await page.getByPlaceholder(/Focus more on pricing strategy/i).fill("Focus on pricing and enterprise segment.");
    await page.getByRole("button", { name: /Approve & Continue to Analysis/i }).click();

    await expect(page.getByText(/Research Complete — Review Before Analysis/i)).not.toBeVisible();
    expect(approvePayload).not.toBeNull();
    expect(approvePayload?.instruction).toBe("Focus on pricing and enterprise segment.");
  });

  test("renders output panel when stream sends complete event", async ({ page }) => {
    await mockAuthenticatedSession(page);
    await mockBackendToken(page);

    let runFetchCount = 0;
    await page.route("**/runs/complete-run", async (route) => {
      runFetchCount += 1;
      const isSecondFetch = runFetchCount > 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "complete-run",
          topic: "AI market brief",
          format: "summary",
          status: isSecondFetch ? "complete" : "writing",
          workspace_id: null,
          vertical: null,
          created_at: "2026-01-01T00:00:00Z",
          logs: [],
          research_output: "Research body",
          final_output: isSecondFetch ? "# Final Brief\n\nDone." : null,
        }),
      });
    });

    await page.route("**/runs/complete-run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: 'data: {"type":"complete","data":{"output":"# Final Brief\\n\\nDone."}}\n\n',
      });
    });

    await page.goto("/runs/complete-run");
    await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
    await expect(page.getByText("Final Brief")).toBeVisible();
    await expect(page.getByRole("link", { name: "Download PDF" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download MD" })).toBeVisible();
  });
});
