/**
 * Demo mode — the whole product, browsable with zero API keys and no backend.
 *
 * Enabled by NEXT_PUBLIC_DEMO=1. Every function in `lib/api.ts` then
 * short-circuits into the in-memory store below instead of calling the backend,
 * and `lib/auth.ts` registers a one-click "demo" provider so there is nothing to
 * sign in *to*.
 *
 * State lives in module-level maps: nothing is persisted, so it survives
 * client-side navigation and dies on a hard reload.
 */

import type {
  AnalyticsCosts,
  AnalyticsMetrics,
  CreateMonitorInput,
  DocumentState,
  LogEntry,
  Monitor,
  Run,
  RunCost,
  RunDetail,
  SSEEvent,
  Workspace,
  WorkspaceMember,
} from "./types";

export const IS_DEMO = process.env.NEXT_PUBLIC_DEMO === "1";

export const DEMO_EMAIL = "demo@research-factory.dev";
export const DEMO_NAME = "Demo User";

/**
 * How the backend would see this user: `lib/auth.ts` namespaces the principal as
 * `<provider>:<email>`. Seed rows that must look owned by the signed-in user
 * have to use exactly this string.
 */
export const DEMO_PRINCIPAL = `demo:${DEMO_EMAIL}`;

// Seed data

// Timestamps are relative to page load, not hard-coded, so the demo never shows
// a "last run: 8 months ago" list that makes the product look abandoned.
const now = Date.now();
const minutesAgo = (m: number) => new Date(now - m * 60_000).toISOString();
const hoursAgo = (h: number) => minutesAgo(h * 60);
const daysAgo = (d: number) => hoursAgo(d * 24);
const inHours = (h: number) => new Date(now + h * 3_600_000).toISOString();

const WS_ACME = "demo-ws-acme";
const WS_PERSONAL = "demo-ws-personal";

function seedWorkspaces(): Workspace[] {
  // Admin in both, matching the `members` seed below, so every action stays
  // reachable rather than gated behind a role the demo user lacks.
  return [
    { id: WS_ACME, name: "Acme Research", owner_id: DEMO_PRINCIPAL, role: "admin" },
    { id: WS_PERSONAL, name: "Personal", owner_id: DEMO_PRINCIPAL, role: "admin" },
  ];
}

function seedMembers(): Record<string, WorkspaceMember[]> {
  return {
    [WS_ACME]: [
      { user_id: DEMO_PRINCIPAL, role: "admin" },
      { user_id: "google:priya@acme.example", role: "operator" },
      { user_id: "google:sam@acme.example", role: "viewer" },
    ],
    [WS_PERSONAL]: [{ user_id: DEMO_PRINCIPAL, role: "admin" }],
  };
}

const COMPETITOR_BRIEF = `# Competitive Brief — Notion (Project Management)

## Executive summary

Notion has moved from "flexible workspace" to an explicit project-management
posture over the last four quarters. The shift shows up in three places at once:
pricing page copy, the Business tier's new timeline and workload views, and a
content program that now targets "Jira alternative" and "Asana alternative"
queries directly rather than generic productivity terms.

For a startup-focused writing product, the practical read is that Notion is
competing for the *team workflow* budget line, not the *individual note-taking*
one. That widens the gap it has to defend and narrows the one you have to.

## Positioning

| Dimension | Notion | Typical PM incumbent |
| --- | --- | --- |
| Primary promise | One workspace replaces four tools | Best-in-class delivery tracking |
| Buyer | Ops lead / founder | Engineering or program manager |
| Expansion path | Seat growth inside a team | Seat growth across departments |
| Weak point | Structure at 200+ person scale | Rigidity for non-eng teams |

## Content strategy

Roughly 60% of new long-form posts in the observed window are comparison or
migration pages. Three patterns are worth copying:

1. **Template-led acquisition.** Every comparison page ends in a duplicable
   template rather than a demo request, which converts to a workspace with real
   data in it — a much stickier activation event than a booked call.
2. **Customer-authored proof.** Case studies are written in the customer's own
   workspace and published as a public page, so the artifact *is* the product.
3. **Migration tooling as content.** Importers are documented as tutorials, and
   those tutorials rank for the incumbent's brand terms.

## Differentiation gaps

- **Reporting depth.** Roll-up reporting across many projects is still weak;
  teams export to a spreadsheet at the point where a portfolio view is needed.
- **Permissions granularity.** Page-level sharing is excellent, field-level
  control is not — a recurring blocker in regulated buyers' evaluations.
- **Offline.** Still the most cited complaint in public review corpora.

## Recommended response

Lead with the reporting gap, not the feature gap. Buyers who churn from a
flexible workspace almost never leave because a feature was missing; they leave
when they cannot answer "what is the status of everything" without manual work.

> **Note on sourcing.** Every claim above traces to a public page captured
> during this run. Nothing here is inferred from private or paywalled material.
`;

const LEAD_INTEL_BRIEF = `# Prospect Dossier — Northwind Logistics

## Company overview

Northwind Logistics is a mid-market freight brokerage operating primarily in the
US Midwest, with a stated headcount in the 300–400 range and a self-described
"technology-forward" repositioning underway since their last funding event.

## Signals worth acting on

- **Hiring.** Four open roles on the data platform team, including a lead
  position. Teams do not hire a platform lead before they intend to buy or build
  platform tooling.
- **Tech stack.** Job postings name Snowflake, dbt, and Airflow — a modern stack,
  which means integration is a selling point rather than an objection.
- **Public commitments.** Their operations lead has spoken twice this year about
  reducing manual quote turnaround, which is the exact metric your product moves.

## Decision makers

| Role | Why they matter | Likely objection |
| --- | --- | --- |
| VP Operations | Owns the turnaround metric | "We already have a process" |
| Head of Data Platform | Owns the integration surface | Build-vs-buy |
| CFO | Signs above the mid-five figures | Payback period |

## Fit score: 82 / 100

Strong operational fit and a live, named pain. The score is held below 90 by a
single unknown: no public evidence of budget cycle timing, so the close date is
unforecastable from open sources alone.

## Suggested opening

Anchor on quote turnaround time, reference their own public statement, and offer
the integration path against the stack their job posts already name.
`;

const STRATEGY_RESEARCH = `## Research summary — AI-assisted legal tooling for SMBs

**Market shape.** The SMB segment is served today by two poorly-fitting options:
enterprise contract-lifecycle suites priced far above SMB willingness to pay, and
generic document templates with no review layer at all. The gap between them is
real and currently unserved.

**Timing signals.**
- Three of the five largest incumbents shipped an AI review feature in the last
  year, which validates demand but also compresses the differentiation window.
- Professional-liability guidance is still unsettled, and that ambiguity is the
  single biggest brake on SMB adoption.

**Competitive density.** Nine funded entrants identified. Seven target law firms
rather than the businesses themselves — the buyer you would be selling to is
comparatively uncontested.

**Open questions for the analysis stage.**
1. Is the wedge document review, or document *generation* with review attached?
2. Does the liability ambiguity argue for a human-in-the-loop requirement as a
   product constraint rather than a feature?
3. What is the realistic ceiling on SMB willingness to pay per seat?

---

*Approve to continue to analysis, or add an instruction to steer it.*
`;

const PERSONAL_SUMMARY = `# Weekly Scan — Retrieval-Augmented Generation

**The short version.** The interesting movement this week was not in retrieval
quality but in retrieval *cost*. Two independent write-ups reported that the
reranking stage, not the embedding stage, dominates their per-query bill.

**Three things worth reading**

1. A production post-mortem on chunking strategy where fixed-size chunks beat
   semantic chunking once the corpus passed a few million documents — the
   opposite of the usual advice, and the reasoning holds up.
2. An evaluation harness release that scores retrieval and generation separately.
   Useful because most reported regressions turn out to be retrieval regressions
   wearing a generation costume.
3. A cost breakdown arguing that hybrid search pays for itself purely by letting
   you retrieve fewer candidates before reranking.

**What this changes for us.** Nothing urgent. Worth revisiting the reranker
budget next time the pipeline is touched.
`;

function seedRuns(): RunDetail[] {
  return [
    {
      id: "demo-competitor-brief",
      topic: "How does Notion position itself against dedicated project management tools?",
      format: "report",
      status: "complete",
      vertical: "marketing_competitor_briefs",
      vertical_inputs: {
        competitor_name: "Notion",
        our_product: "AI writing assistant for startups",
        target_market: "Series A SaaS founders",
      },
      created_at: hoursAgo(3),
      workspace_id: WS_ACME,
      logs: [
        { agent: "system", message: "Status changed to researching", ts: hoursAgo(3) },
        { agent: "Researcher", message: "Searching for Notion positioning, pricing, and comparison pages", ts: hoursAgo(3) },
        { agent: "Researcher", message: "Found 14 sources; scraping the 6 highest-signal pages", ts: hoursAgo(3) },
        { agent: "Researcher", message: "Extracted 9 findings across positioning, pricing, and content", ts: hoursAgo(3) },
        { agent: "system", message: "Human approval required at awaiting_research_approval", ts: hoursAgo(3) },
        { agent: "system", message: "Research approved — continuing to analysis", ts: hoursAgo(3) },
        { agent: "Analyst", message: "Clustered findings into positioning, content strategy, and gaps", ts: hoursAgo(2) },
        { agent: "Analyst", message: "Identified 3 differentiation gaps with supporting evidence", ts: hoursAgo(2) },
        { agent: "Writer", message: "Drafted the brief in report format", ts: hoursAgo(2) },
        { agent: "Editor", message: "Tightened the executive summary and verified every claim has a source", ts: hoursAgo(2) },
        { agent: "system", message: "Run completed", ts: hoursAgo(2) },
      ],
      research_output: "Raw research notes across 14 sources, 6 scraped in full.",
      analysis_output: "Positioning shift confirmed; three defensible gaps identified.",
      final_output: COMPETITOR_BRIEF,
      metrics: {
        latency_sec: 214,
        eval_scores: {
          accuracy: 88,
          relevance: 94,
          completeness: 81,
          writing_quality: 90,
          overall: 88,
          issues: ["Pricing tiers were captured from a single regional page and may vary by market."],
        },
        // One unverified source on purpose: agents do cite pages they never
        // fetched, so the demo shows that case and not only the clean one.
        citations: [
          { source: "Northwind pricing page", page: "https://northwind-logistics.example/pricing", verified: true },
          { source: "Q3 partner announcement", page: "https://northwind-logistics.example/press/q3-partners", verified: true },
          { source: "Freight Weekly market review", page: "https://freight-weekly.example/market-review", verified: true },
          { source: "industry analysts", page: "https://logistics-analysts.example/report", verified: false },
        ],
      },
      // Researcher runs twice — once to plan, once after the approval gate —
      // which is why the panel folds rows per agent rather than listing calls.
      costs: seedCosts("demo-competitor-brief", hoursAgo(2), [
        ["Researcher", 18_420, 3_180, 0.0139],
        ["Researcher", 6_910, 1_240, 0.0052],
        ["Analyst", 14_760, 4_020, 0.0171],
        ["Writer", 9_340, 5_610, 0.0203],
        ["Editor", 7_120, 1_890, 0.0065],
        ["eval_judge", 5_480, 640, 0.0027],
      ]),
    },
    {
      id: "demo-lead-intel",
      topic: "Prospect dossier for Northwind Logistics",
      format: "report",
      status: "complete",
      vertical: "b2b_sales_lead_intel",
      vertical_inputs: {
        company_url: "https://northwind-logistics.example",
        target_role: "VP Operations",
        our_product: "Automated freight quoting",
      },
      created_at: hoursAgo(20),
      workspace_id: WS_ACME,
      monitor_id: "demo-monitor-northwind",
      logs: [
        { agent: "system", message: "Status changed to researching", ts: hoursAgo(20) },
        { agent: "Researcher", message: "Collected hiring signals, tech stack mentions, and public statements", ts: hoursAgo(20) },
        { agent: "Analyst", message: "Scored fit against the stated value proposition", ts: hoursAgo(20) },
        { agent: "Writer", message: "Drafted the dossier", ts: hoursAgo(20) },
        { agent: "system", message: "Run completed", ts: hoursAgo(20) },
      ],
      research_output: "Hiring, stack, and public-statement signals collected from 11 sources.",
      analysis_output: "Fit score 82/100; budget timing unknown from open sources.",
      final_output: LEAD_INTEL_BRIEF,
      metrics: {
        latency_sec: 173,
        eval_scores: {
          accuracy: 79,
          relevance: 91,
          completeness: 74,
          writing_quality: 86,
          overall: 82,
          issues: [
            "No separate research artifact for this playbook, so accuracy is scored against the output itself.",
            "Headcount is a self-reported range, not a verified figure.",
          ],
        },
        monitor_diff: {
          changed: true,
          summary:
            "Two new data-platform roles opened since the previous run, and the operations lead repeated the quote-turnaround commitment publicly.",
          highlights: [
            "Data platform headcount target moved from 2 to 4 open roles",
            "Snowflake and dbt now named explicitly in job requirements",
            "No change to the published leadership team",
          ],
        },
      },
      costs: seedCosts("demo-lead-intel", hoursAgo(20), [
        ["Researcher", 12_880, 2_450, 0.0098],
        ["Analyst", 9_610, 3_140, 0.0122],
        ["Writer", 7_220, 4_180, 0.0154],
        ["eval_judge", 4_930, 580, 0.0024],
        ["monitor_diff", 6_340, 720, 0.0031],
      ]),
    },
    {
      id: "demo-strategy-review",
      topic: "Is now the right time to enter the SMB legal tech market?",
      format: "summary",
      status: "awaiting_research_approval",
      vertical: "founder_strategy_briefs",
      vertical_inputs: {
        market_segment: "AI-powered legal tech for SMBs",
        stage: "Pre-seed",
        key_question: "Is now the right time to enter the SMB legal market?",
      },
      created_at: minutesAgo(12),
      workspace_id: WS_ACME,
      logs: [
        { agent: "system", message: "Status changed to researching", ts: minutesAgo(12) },
        { agent: "Researcher", message: "Mapped the incumbent landscape and recent AI feature launches", ts: minutesAgo(11) },
        { agent: "Researcher", message: "Identified 9 funded entrants; 7 target law firms rather than SMBs", ts: minutesAgo(10) },
        { agent: "system", message: "Human approval required at awaiting_research_approval", ts: minutesAgo(9) },
      ],
      research_output: STRATEGY_RESEARCH,
      analysis_output: null,
      final_output: null,
    },
    {
      id: "demo-failed-run",
      topic: "Pricing changes across enterprise observability vendors",
      format: "report",
      status: "failed",
      failed_at_status: "researching",
      vertical: null,
      created_at: daysAgo(2),
      workspace_id: WS_ACME,
      logs: [
        { agent: "system", message: "Status changed to researching", ts: daysAgo(2) },
        { agent: "Researcher", message: "Search returned 8 results", ts: daysAgo(2) },
        { agent: "error", message: "Page scraping unavailable for 6 of 8 sources (Firecrawl: TimeoutError)", ts: daysAgo(2) },
        { agent: "error", message: "Insufficient source material to continue to analysis", ts: daysAgo(2) },
      ],
      research_output: null,
      analysis_output: null,
      final_output: null,
      error_message:
        "Run failed: not enough sources could be retrieved. 6 of 8 pages timed out during scraping.",
      // A failed run still spent money before it died; the cost panel renders
      // outside the "complete" branch so that spend is still reported.
      costs: seedCosts("demo-failed-run", daysAgo(2), [
        ["Researcher", 8_140, 1_260, 0.0057],
      ]),
    },
    {
      id: "demo-personal-scan",
      topic: "Weekly scan: what changed in retrieval-augmented generation",
      format: "summary",
      status: "complete",
      vertical: null,
      created_at: daysAgo(1),
      workspace_id: WS_PERSONAL,
      logs: [
        { agent: "system", message: "Status changed to researching", ts: daysAgo(1) },
        { agent: "Researcher", message: "Scanned 22 sources published in the last 7 days", ts: daysAgo(1) },
        { agent: "Writer", message: "Drafted the weekly summary", ts: daysAgo(1) },
        { agent: "system", message: "Run completed", ts: daysAgo(1) },
      ],
      research_output: "22 sources scanned, 3 with material updates.",
      analysis_output: "Cost, not quality, was the week's actual movement.",
      final_output: PERSONAL_SUMMARY,
      metrics: {
        latency_sec: 96,
        eval_scores: { accuracy: 84, relevance: 88, completeness: 71, writing_quality: 92, overall: 84 },
      },
      costs: seedCosts("demo-personal-scan", daysAgo(1), [
        ["Researcher", 21_300, 1_980, 0.0128],
        ["Writer", 5_640, 3_020, 0.0113],
        ["eval_judge", 4_110, 520, 0.0021],
      ]),
    },
  ];
}

/**
 * Build the `run_costs` rows a run would have accumulated.
 *
 * The backend writes one row per LLM call, so an agent that ran twice gets two
 * rows; the seed keeps that shape rather than pre-summing, because folding rows
 * per agent is the cost panel's job.
 *
 * These figures are a *paid*-model scenario. A default deployment routes to
 * free-tier models and really does spend $0 — the scripted live run below covers
 * that branch of the display.
 */
let costRowSeq = 0;
function seedCosts(
  runId: string,
  at: string,
  rows: [agent: string, input: number, output: number, usd: number][],
): RunCost[] {
  return rows.map(([agent_name, input_tokens, output_tokens, total_cost]) => ({
    id: `demo-cost-${++costRowSeq}`,
    run_id: runId,
    agent_name,
    input_tokens,
    output_tokens,
    total_cost,
    created_at: at,
  }));
}

function seedMonitors(): Monitor[] {
  return [
    {
      id: "demo-monitor-northwind",
      user_id: DEMO_PRINCIPAL,
      workspace_id: WS_ACME,
      name: "Northwind Logistics — account watch",
      topic: "Prospect dossier for Northwind Logistics",
      format: "report",
      vertical: "b2b_sales_lead_intel",
      vertical_inputs: { company_url: "https://northwind-logistics.example" },
      interval_minutes: 1440,
      enabled: true,
      next_run_at: inHours(4),
      last_run_id: "demo-lead-intel",
      last_run_at: hoursAgo(20),
      notify_channel: "demo@research-factory.dev",
      created_at: daysAgo(9),
      updated_at: hoursAgo(20),
    },
    {
      id: "demo-monitor-pricing",
      user_id: DEMO_PRINCIPAL,
      workspace_id: WS_ACME,
      name: "Competitor pricing pages",
      topic: "Pricing and packaging changes across our three named competitors",
      format: "summary",
      vertical: "marketing_competitor_briefs",
      interval_minutes: 10080,
      enabled: false,
      next_run_at: inHours(72),
      last_run_id: null,
      last_run_at: null,
      notify_channel: null,
      created_at: daysAgo(4),
      updated_at: daysAgo(4),
    },
  ];
}

// Store

const workspaces: Workspace[] = seedWorkspaces();
const members: Record<string, WorkspaceMember[]> = seedMembers();
/**
 * Uploaded docs, keyed by doc id. Nothing is parsed or indexed, but the
 * pending → ready transition is modelled on a timer because real ingestion
 * happens in a worker after the upload responds — returning "ready" instantly
 * would hide the state the upload UI exists to show.
 */
const documents = new Map<string, { filename: string; readyAt: number }>();
const DEMO_INGEST_MS = 2_000;
const runs = new Map<string, RunDetail>(seedRuns().map((r) => [r.id, r]));
const monitors = new Map<string, Monitor>(seedMonitors().map((m) => [m.id, m]));

/** Network latency stand-in, so loading states and skeletons are actually visible. */
const LATENCY_MS = 220;
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
async function respond<T>(value: T): Promise<T> {
  await sleep(LATENCY_MS);
  return value;
}

/** Strip the detail-only fields, the way the list endpoint does. */
function toListItem(run: RunDetail): Run {
  return {
    id: run.id,
    topic: run.topic,
    format: run.format,
    status: run.status,
    failed_at_status: run.failed_at_status,
    vertical: run.vertical,
    vertical_inputs: run.vertical_inputs,
    created_at: run.created_at,
    monitor_id: run.monitor_id,
    workspace_id: run.workspace_id,
  };
}

function byNewestFirst<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

// Live run streaming

type Listener = (event: SSEEvent) => void;

const listeners = new Map<string, Set<Listener>>();
/** Runs whose script hasn't been started yet, keyed by run id. */
const pendingScripts = new Map<string, () => void>();
/** Resolvers for runs parked at a human-approval gate, keyed by run id. */
const approvalGates = new Map<string, () => void>();

function emit(id: string, event: SSEEvent) {
  listeners.get(id)?.forEach((listener) => listener(event));
}

/**
 * Subscribe to a run's live events, replacing the SSE connection.
 *
 * A newly created run's script only starts on the first subscribe: otherwise the
 * scripted logs could fire between `createRun` returning and the run page
 * mounting its stream, and the first few lines would silently vanish.
 */
export function subscribeToDemoRun(id: string, listener: Listener): () => void {
  const set = listeners.get(id) ?? new Set<Listener>();
  set.add(listener);
  listeners.set(id, set);

  const start = pendingScripts.get(id);
  if (start) {
    pendingScripts.delete(id);
    start();
  }

  return () => {
    set.delete(listener);
    if (set.size === 0) listeners.delete(id);
  };
}

function appendLog(id: string, agent: string, message: string) {
  const entry: LogEntry = { agent, message, ts: new Date().toISOString() };
  runs.get(id)?.logs.push(entry);
  emit(id, { type: "log", data: entry });
}

function setStatus(id: string, status: RunDetail["status"]) {
  const run = runs.get(id);
  if (run) run.status = status;
  emit(id, { type: "status", data: { status } });
}

function waitForApproval(id: string): Promise<void> {
  return new Promise<void>((resolve) => approvalGates.set(id, resolve));
}

const BEAT = 850;

/**
 * The scripted pipeline a demo run walks through.
 *
 * It pauses at the research gate rather than running start to finish, so the
 * human-in-the-loop checkpoint has to be exercised by hand.
 */
async function playRunScript(id: string, topic: string) {
  await sleep(BEAT / 2);
  setStatus(id, "researching");
  appendLog(id, "Researcher", `Planning research for “${topic}”`);

  await sleep(BEAT);
  appendLog(id, "Researcher", "Searching the web — 12 candidate sources found");

  await sleep(BEAT);
  appendLog(id, "Researcher", "Scraping the 5 highest-signal pages for full text");

  await sleep(BEAT);
  appendLog(id, "Researcher", "Synthesized 8 findings and dropped 3 low-confidence claims");

  await sleep(BEAT);
  const summary = DEMO_RUN_RESEARCH;
  const run = runs.get(id);
  if (run) {
    run.research_output = summary;
    run.status = "awaiting_research_approval";
  }
  emit(id, {
    type: "hitl_required",
    data: { stage: "awaiting_research_approval", summary },
  });

  await waitForApproval(id);

  appendLog(id, "system", "Research approved — continuing to analysis");
  setStatus(id, "analyzing");

  await sleep(BEAT);
  appendLog(id, "Analyst", "Clustered findings into themes and weighed the evidence behind each");

  await sleep(BEAT);
  const analysis = "Three themes with supporting evidence; one contested claim flagged for the writer.";
  const analysing = runs.get(id);
  if (analysing) analysing.analysis_output = analysis;
  setStatus(id, "writing");
  appendLog(id, "Writer", "Drafting the output in the requested format");

  await sleep(BEAT);
  appendLog(id, "Editor", "Tightened the summary and checked every claim against a source");

  await sleep(BEAT);
  const final = demoFinalOutput(topic);
  const finished = runs.get(id);
  if (finished) {
    finished.final_output = final;
    finished.status = "complete";
    finished.metrics = {
      latency_sec: 9,
      eval_scores: {
        accuracy: 86,
        relevance: 92,
        completeness: 78,
        writing_quality: 89,
        overall: 86,
        issues: ["Demo output — generated from a fixed script, not from live sources."],
      },
    };
    // Zero-cost on purpose: a default deployment routes every agent to a
    // free-tier model, so this is what a freshly configured install records.
    finished.costs = seedCosts(id, new Date().toISOString(), [
      ["Researcher", 11_240, 2_060, 0],
      ["Analyst", 8_470, 2_910, 0],
      ["Writer", 6_180, 3_740, 0],
      ["Editor", 5_020, 1_130, 0],
      ["eval_judge", 3_960, 480, 0],
    ]);
  }
  emit(id, { type: "complete", data: { final_output: final } });
}

const DEMO_RUN_RESEARCH = `## Research summary

Eight findings survived the confidence filter, drawn from 12 candidate sources of
which 5 were scraped in full.

**What the sources agree on**
- The category's centre of gravity moved in the last two quarters, and the move
  is visible in pricing and packaging before it is visible in messaging.
- Buyers consistently name reporting depth, not feature count, as the reason
  they switch.

**What they disagree on**
- Whether the shift is durable or a response to a single competitor's launch.
  Three sources argue each way; the disagreement is genuine, not a sourcing gap.

**Dropped as low-confidence**
- Two revenue figures traceable to a single unattributed blog post.
- One headcount claim contradicted by the company's own careers page.

---

*This is the human-in-the-loop checkpoint. Approve to continue to analysis, or
add an instruction to steer what happens next.*
`;

function demoFinalOutput(topic: string): string {
  return `# ${topic}

## Executive summary

This report was produced by the demo pipeline: a scripted walk through the same
researcher → human review → analyst → writer → editor path a live run takes, with
the model calls replaced by fixed text. The structure, the streaming log, the
approval gate, and the scoring below are all the real components.

## Key findings

1. **The move happened in packaging first.** Pricing and tier structure changed a
   quarter before the messaging did, which is the usual order and makes pricing
   pages the highest-signal thing to monitor.
2. **Reporting depth drives switching.** Across the sources that discussed churn,
   the stated reason was almost never a missing feature — it was the inability to
   answer a portfolio-level question without manual work.
3. **The durability question is genuinely open.** The sources disagree, and that
   disagreement was preserved here rather than resolved by picking a side.

## What was deliberately not concluded

The research stage dropped two revenue figures and one headcount claim for
insufficient sourcing. They are absent from this report rather than hedged into
it — an analysis is more useful when you can tell what it declined to say.

## Next steps

- Set this up as a monitor to catch the next packaging change automatically.
- Re-run with a narrower topic if you want depth on a single competitor.

---

*Demo output. Connect a real backend and an LLM key to run this for real.*
`;
}

// The API surface: one function per export in `lib/api.ts`, same signatures,
// same shapes.

export const demoApi = {
  async authHeaders(): Promise<Record<string, string>> {
    // No backend to authenticate against; returning a header rather than
    // throwing keeps every caller's happy path identical to production.
    return { Authorization: "Bearer demo-mode" };
  },

  async createRun(payload: {
    topic: string;
    format: string;
    doc_ids: string[];
    workspace_id?: string;
    vertical?: string;
    vertical_inputs?: Record<string, string>;
  }): Promise<{ id: string }> {
    const id = `demo-run-${Math.random().toString(36).slice(2, 9)}`;
    const run: RunDetail = {
      id,
      topic: payload.topic,
      format: payload.format as RunDetail["format"],
      status: "pending",
      vertical: (payload.vertical as RunDetail["vertical"]) ?? null,
      vertical_inputs: payload.vertical_inputs,
      created_at: new Date().toISOString(),
      workspace_id: payload.workspace_id ?? null,
      logs: [],
      research_output: null,
      analysis_output: null,
      final_output: null,
    };
    runs.set(id, run);
    pendingScripts.set(id, () => void playRunScript(id, payload.topic));
    return respond({ id });
  },

  async getRuns(workspaceId?: string): Promise<Run[]> {
    const all = [...runs.values()].filter((r) =>
      workspaceId ? r.workspace_id === workspaceId : true,
    );
    return respond(byNewestFirst(all).map(toListItem));
  },

  async getRun(id: string): Promise<RunDetail> {
    const run = runs.get(id);
    if (!run) throw new Error(`Run ${id} was not found in the demo dataset.`);
    // Cloned so a consumer holding the previous object still sees a change.
    return respond({ ...run, logs: [...run.logs] });
  },

  async approveHitl(id: string, instruction?: string) {
    if (instruction?.trim()) {
      appendLog(id, "system", `Reviewer instruction: ${instruction.trim()}`);
    }
    const resume = approvalGates.get(id);
    if (resume) {
      approvalGates.delete(id);
      resume();
      return respond({ status: "resumed" });
    }
    // A seeded run parked at the gate has no script behind it; advance it far
    // enough that the UI reacts, rather than silently doing nothing.
    setStatus(id, "analyzing");
    appendLog(id, "system", "Research approved — continuing to analysis");
    return respond({ status: "resumed" });
  },

  async uploadFile(file: File, workspaceId: string): Promise<{ doc_id: string }> {
    // Nothing is parsed or indexed — the demo accepts the file so the upload UI
    // is reachable, and the resulting doc_id is inert as run context.
    await sleep(600);
    const slug = file.name.replace(/\W+/g, "-").toLowerCase();
    const docId = `demo-doc-${workspaceId}-${slug}`;
    documents.set(docId, { filename: file.name, readyAt: Date.now() + DEMO_INGEST_MS });
    return { doc_id: docId };
  },

  async getDocument(docId: string): Promise<DocumentState> {
    const doc = documents.get(docId);
    if (!doc) throw new Error(`Document ${docId} was not found in the demo dataset.`);
    const ready = Date.now() >= doc.readyAt;
    return respond({
      doc_id: docId,
      filename: doc.filename,
      status: ready ? "ready" : "pending",
      chunk_count: ready ? 24 : null,
      error_message: null,
    });
  },

  /**
   * Mirrors `GET /analytics/metrics`, including its scoping quirk: **completed
   * runs only**. A failed run has nothing to score, so it is absent here while
   * its spend still shows up in `getAnalyticsCosts` below — the two panels count
   * different populations.
   */
  async getAnalyticsMetrics(workspaceId?: string): Promise<AnalyticsMetrics> {
    const scoped = [...runs.values()].filter(
      (r) => (workspaceId ? r.workspace_id === workspaceId : true) && r.status === "complete",
    );
    const withMetrics = scoped.map((r) => r.metrics).filter((m) => !!m);
    if (withMetrics.length === 0) return respond({ count: 0, averages: {} });

    const count = withMetrics.length;
    const scores = withMetrics.map((m) => m.eval_scores).filter((s) => !!s);
    const avgScore = (key: keyof NonNullable<(typeof scores)[number]>) =>
      scores.length
        ? scores.reduce((sum, s) => sum + (typeof s[key] === "number" ? (s[key] as number) : 0), 0) / scores.length
        : 0;

    return respond({
      count,
      averages: {
        latency_sec: withMetrics.reduce((sum, m) => sum + (m.latency_sec ?? 0), 0) / count,
        citations: withMetrics.reduce((sum, m) => sum + (m.citations?.length ?? 0), 0) / count,
        accuracy: avgScore("accuracy"),
        relevance: avgScore("relevance"),
        completeness: avgScore("completeness"),
        writing_quality: avgScore("writing_quality"),
        overall: avgScore("overall"),
      },
    });
  },

  /** Mirrors `GET /analytics/costs` — every run in scope, failed ones included.
   *  Derived from the same rows the run pages show, so the workspace total and
   *  the per-run panels can never disagree. */
  async getAnalyticsCosts(workspaceId?: string): Promise<AnalyticsCosts> {
    const rows = [...runs.values()]
      .filter((r) => (workspaceId ? r.workspace_id === workspaceId : true))
      .flatMap((r) => r.costs ?? []);

    const perAgent = new Map<string, { cost: number; input_tokens: number; output_tokens: number }>();
    for (const row of rows) {
      const agent = perAgent.get(row.agent_name) ?? { cost: 0, input_tokens: 0, output_tokens: 0 };
      agent.cost += row.total_cost;
      agent.input_tokens += row.input_tokens;
      agent.output_tokens += row.output_tokens;
      perAgent.set(row.agent_name, agent);
    }

    return respond({
      total_cost_usd: rows.reduce((sum, r) => sum + r.total_cost, 0),
      total_input_tokens: rows.reduce((sum, r) => sum + r.input_tokens, 0),
      total_output_tokens: rows.reduce((sum, r) => sum + r.output_tokens, 0),
      per_agent: [...perAgent.entries()].map(([agent_name, totals]) => ({ agent_name, ...totals })),
    });
  },

  async getWorkspaces(): Promise<Workspace[]> {
    return respond([...workspaces]);
  },

  async createWorkspace(name: string): Promise<Workspace> {
    const ws: Workspace = {
      id: `demo-ws-${Math.random().toString(36).slice(2, 8)}`,
      name,
      owner_id: DEMO_PRINCIPAL,
      role: "admin",
    };
    workspaces.push(ws);
    members[ws.id] = [{ user_id: DEMO_PRINCIPAL, role: "admin" }];
    return respond(ws);
  },

  async getWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
    return respond([...(members[workspaceId] ?? [])]);
  },

  async addWorkspaceMember(workspaceId: string, userId: string, role: string): Promise<void> {
    const list = members[workspaceId] ?? (members[workspaceId] = []);
    const existing = list.find((m) => m.user_id === userId);
    if (existing) existing.role = role as WorkspaceMember["role"];
    else list.push({ user_id: userId, role: role as WorkspaceMember["role"] });
    await sleep(LATENCY_MS);
  },

  async removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
    members[workspaceId] = (members[workspaceId] ?? []).filter((m) => m.user_id !== userId);
    await sleep(LATENCY_MS);
  },

  async getMonitors(workspaceId?: string): Promise<Monitor[]> {
    const all = [...monitors.values()].filter((m) =>
      workspaceId ? m.workspace_id === workspaceId : true,
    );
    return respond(byNewestFirst(all));
  },

  async getMonitor(id: string): Promise<Monitor> {
    const monitor = monitors.get(id);
    if (!monitor) throw new Error(`Monitor ${id} was not found in the demo dataset.`);
    return respond({ ...monitor });
  },

  async getMonitorRuns(id: string): Promise<Run[]> {
    const all = [...runs.values()].filter((r) => r.monitor_id === id);
    return respond(byNewestFirst(all).map(toListItem));
  },

  async createMonitor(payload: CreateMonitorInput): Promise<Monitor> {
    const monitor: Monitor = {
      id: `demo-monitor-${Math.random().toString(36).slice(2, 8)}`,
      user_id: DEMO_PRINCIPAL,
      workspace_id: payload.workspace_id ?? null,
      name: payload.name,
      topic: payload.topic,
      format: payload.format,
      vertical: null,
      interval_minutes: payload.interval_minutes,
      enabled: payload.enabled,
      next_run_at: new Date(Date.now() + payload.interval_minutes * 60_000).toISOString(),
      last_run_id: null,
      last_run_at: null,
      notify_channel: payload.notify_channel ?? null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    monitors.set(monitor.id, monitor);
    return respond(monitor);
  },

  async updateMonitor(
    id: string,
    patch: Partial<Pick<Monitor, "name" | "interval_minutes" | "enabled" | "notify_channel">>,
  ): Promise<Monitor> {
    const monitor = monitors.get(id);
    if (!monitor) throw new Error(`Monitor ${id} was not found in the demo dataset.`);
    Object.assign(monitor, patch, { updated_at: new Date().toISOString() });
    return respond({ ...monitor });
  },

  async runMonitorNow(id: string): Promise<{ id: string }> {
    const monitor = monitors.get(id);
    if (!monitor) throw new Error(`Monitor ${id} was not found in the demo dataset.`);
    const created = await demoApi.createRun({
      topic: monitor.topic,
      format: monitor.format,
      doc_ids: [],
      workspace_id: monitor.workspace_id ?? undefined,
      vertical: monitor.vertical ?? undefined,
    });
    const run = runs.get(created.id);
    if (run) run.monitor_id = id;
    monitor.last_run_id = created.id;
    monitor.last_run_at = new Date().toISOString();
    return created;
  },

  async deleteMonitor(id: string): Promise<void> {
    monitors.delete(id);
    await sleep(LATENCY_MS);
  },

  async downloadOutput(runId: string, format: "pdf" | "md"): Promise<void> {
    const run = runs.get(runId);
    if (!run?.final_output) throw new Error("This run has no output to download yet.");
    if (format === "pdf") {
      // The real PDF is rendered server-side; the demo declines rather than
      // handing over a .pdf that is really markdown.
      throw new Error(
        "PDF export is rendered by the backend, so it's unavailable in demo mode. Download MD for the full report.",
      );
    }
    const blob = new Blob([run.final_output], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${runId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
