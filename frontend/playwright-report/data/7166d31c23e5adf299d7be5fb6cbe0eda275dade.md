# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> Core Flow Smoke Tests >> shows the real backend error message when a run fails during a live session
- Location: e2e/smoke.spec.ts:259:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('This run failed. Check the agent logs above for details.')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText('This run failed. Check the agent logs above for details.')

```

```yaml
- complementary:
  - link "Research Factory":
    - /url: /
    - img
    - text: Research Factory
  - link "New Run":
    - /url: /new
    - img
    - text: New Run
  - navigation:
    - link "History":
      - /url: /
      - img
      - text: History
  - button "Switch to light mode":
    - img
    - text: Light mode
  - paragraph: Test User
  - paragraph: test@example.com
  - button "Sign out":
    - img
    - text: Sign out
- main:
  - paragraph: Cannot read properties of undefined (reading 'replace')
- alert
- button "Open Next.js Dev Tools":
  - img
```

# Test source

```ts
  201 |         status: 200,
  202 |         contentType: "application/json",
  203 |         body: JSON.stringify({
  204 |           id: "complete-run",
  205 |           topic: "AI market brief",
  206 |           format: "summary",
  207 |           status: "writing",
  208 |           workspace_id: null,
  209 |           vertical: null,
  210 |           created_at: "2026-01-01T00:00:00Z",
  211 |           logs: [],
  212 |           research_output: "Research body",
  213 |           final_output: null,
  214 |         }),
  215 |       });
  216 |       await page.unroute("**/runs/complete-run", mockCompleteRunFirst);
  217 |       await page.route("**/runs/complete-run", async (route) => {
  218 |         if (route.request().isNavigationRequest()) {
  219 |           await route.continue();
  220 |           return;
  221 |         }
  222 |         await route.fulfill({
  223 |           status: 200,
  224 |           contentType: "application/json",
  225 |           body: JSON.stringify({
  226 |             id: "complete-run",
  227 |             topic: "AI market brief",
  228 |             format: "summary",
  229 |             status: "complete",
  230 |             workspace_id: null,
  231 |             vertical: null,
  232 |             created_at: "2026-01-01T00:00:00Z",
  233 |             logs: [],
  234 |             research_output: "Research body",
  235 |             final_output: "# Final Brief\n\nDone.",
  236 |           }),
  237 |         });
  238 |       });
  239 |     }
  240 | 
  241 |     await page.route("**/runs/complete-run", mockCompleteRunFirst);
  242 | 
  243 |     await page.route("**/runs/complete-run/stream", async (route) => {
  244 |       await route.fulfill({
  245 |         status: 200,
  246 |         headers: { "content-type": "text/event-stream" },
  247 |         body: 'retry: 10000\ndata: {"type":"complete","data":{"final_output":"# Final Brief\\n\\nDone."}}\n\n',
  248 |       });
  249 |     });
  250 | 
  251 |     await createSessionCookie(page);
  252 |     await page.goto("/runs/complete-run");
  253 |     await expect(page.getByRole("heading", { name: "Output" })).toBeVisible();
  254 |     await expect(page.getByText("Final Brief")).toBeVisible();
  255 |     await expect(page.getByRole("button", { name: "Download PDF" })).toBeVisible();
  256 |     await expect(page.getByRole("button", { name: "Download MD" })).toBeVisible();
  257 |   });
  258 | 
  259 |   test("shows the real backend error message when a run fails during a live session", async ({ page }) => {
  260 |     // §10.1 regression: the "error" stream event used to only flip status to
  261 |     // "failed" without storing parsed.data.message, so the banner fell back to
  262 |     // run.error_message — null for a run that fails after the page already loaded.
  263 |     await mockAuthenticatedSession(page);
  264 |     await mockBackendToken(page);
  265 | 
  266 |     await page.route("**/runs/failing-run", async (route) => {
  267 |       if (route.request().isNavigationRequest()) {
  268 |         await route.continue();
  269 |         return;
  270 |       }
  271 |       await route.fulfill({
  272 |         status: 200,
  273 |         contentType: "application/json",
  274 |         body: JSON.stringify({
  275 |           id: "failing-run",
  276 |           topic: "AI market brief",
  277 |           format: "summary",
  278 |           status: "researching",
  279 |           workspace_id: null,
  280 |           vertical: null,
  281 |           created_at: "2026-01-01T00:00:00Z",
  282 |           logs: [],
  283 |           research_output: null,
  284 |           final_output: null,
  285 |           error_message: null,
  286 |         }),
  287 |       });
  288 |     });
  289 | 
  290 |     await page.route("**/runs/failing-run/stream", async (route) => {
  291 |       await route.fulfill({
  292 |         status: 200,
  293 |         headers: { "content-type": "text/event-stream" },
  294 |         body: 'retry: 10000\ndata: {"type":"error","data":{"message":"Run failed: rate limit exceeded"}}\n\n',
  295 |       });
  296 |     });
  297 | 
  298 |     await createSessionCookie(page);
  299 |     await page.goto("/runs/failing-run");
  300 | 
> 301 |     await expect(page.getByText("This run failed. Check the agent logs above for details.")).toBeVisible();
      |                                                                                              ^ Error: expect(locator).toBeVisible() failed
  302 |     await expect(page.getByText("Run failed: rate limit exceeded")).toBeVisible();
  303 |   });
  304 | });
  305 | 
```