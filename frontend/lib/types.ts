export type RunStatus =
  | "pending"
  | "researching"
  | "awaiting_hitl"
  | "awaiting_research_approval"
  | "analyzing"
  | "awaiting_analysis_approval"
  | "writing"
  | "awaiting_final_approval"
  | "complete"
  | "failed";

export type SSEEvent =
  | { type: "status"; data: { status: RunStatus } }
  | { type: "log"; data: LogEntry }
  | { type: "hitl_required"; data: { stage: string; summary: string } }
  | { type: "complete"; data: { final_output: string } }
  | { type: "error"; data: { message: string } };

export type OutputFormat = "report" | "linkedin" | "summary";

export type Vertical =
  | "b2b_sales_lead_intel"
  | "marketing_competitor_briefs"
  | "founder_strategy_briefs";

export interface VerticalFieldSchema {
  label: string;
  required: boolean;
  placeholder: string;
  type: "text" | "url" | "select";
  options?: string[];
}

export interface VerticalDefinition {
  key: Vertical;
  displayName: string;
  description: string;
  inputSchema: Record<string, VerticalFieldSchema>;
  defaultFormat: OutputFormat;
  accentClass: string;
}

export const VERTICALS: VerticalDefinition[] = [
  {
    key: "b2b_sales_lead_intel",
    displayName: "B2B Sales Lead Intel",
    description:
      "Build a prospect dossier — company overview, decision makers, funding, tech stack, and fit score.",
    defaultFormat: "report",
    accentClass: "text-content bg-category-sales/10 border-category-sales/40",
    inputSchema: {
      company_url: {
        label: "Company URL",
        required: true,
        placeholder: "https://acme.com",
        type: "url",
      },
      target_role: {
        label: "Target Buyer Role",
        required: false,
        placeholder: "e.g. Head of Engineering, VP Sales",
        type: "text",
      },
      our_product: {
        label: "Your Product / Value Prop",
        required: false,
        placeholder: "Brief description of what you sell",
        type: "text",
      },
    },
  },
  {
    key: "marketing_competitor_briefs",
    displayName: "Marketing Competitor Brief",
    description:
      "Analyze a competitor's positioning, content strategy, pricing, and differentiation gaps.",
    defaultFormat: "report",
    accentClass: "text-content bg-category-competitor/10 border-category-competitor/40",
    inputSchema: {
      competitor_name: {
        label: "Competitor Name",
        required: true,
        placeholder: "e.g. Notion, Salesforce, HubSpot",
        type: "text",
      },
      our_product: {
        label: "Your Product / Category",
        required: false,
        placeholder: "e.g. AI writing assistant for startups",
        type: "text",
      },
      target_market: {
        label: "Target Market / ICP",
        required: false,
        placeholder: "e.g. Series A SaaS founders, SMB marketing teams",
        type: "text",
      },
    },
  },
  {
    key: "founder_strategy_briefs",
    displayName: "Founder Strategy Brief",
    description:
      "Get a strategic landscape analysis — market sizing, competition, timing, and entry points.",
    defaultFormat: "summary",
    accentClass: "text-content bg-category-strategy/10 border-category-strategy/40",
    inputSchema: {
      market_segment: {
        label: "Market Segment",
        required: true,
        placeholder: "e.g. AI-powered legal tech for SMBs",
        type: "text",
      },
      stage: {
        label: "Company Stage",
        required: false,
        placeholder: "Select stage",
        type: "select",
        options: ["Pre-idea", "Pre-seed", "Seed", "Series A", "Series B+"],
      },
      key_question: {
        label: "Key Strategic Question",
        required: false,
        placeholder: "e.g. Is now the right time to enter the SMB legal market?",
        type: "text",
      },
    },
  },
];

export interface Run {
  id: string;
  /** Principal who started the run (`<provider>:<email>`). Absent means
   *  "ownership unknown" — never read it as "not the owner". */
  user_id?: string;
  topic: string;
  format: OutputFormat;
  status: RunStatus;
  /** Last active stage before the run failed. Only set when status is "failed". */
  failed_at_status?: RunStatus | null;
  vertical?: Vertical | null;
  vertical_inputs?: Record<string, string>;
  created_at: string;
  monitor_id?: string | null;
  /** Null for a personal run. The list endpoint filters on it server-side. */
  workspace_id?: string | null;
}

/** LLM-judge quality scores (0–100 per dimension) computed once a run completes. */
export interface EvalScores {
  accuracy?: number;
  relevance?: number;
  completeness?: number;
  writing_quality?: number;
  overall?: number;
  issues?: string[];
}

/** Change-detection result for a monitored run vs. the monitor's previous run. */
export interface MonitorDiff {
  changed: boolean;
  summary: string;
  highlights?: string[];
  baseline?: boolean;
}

/** A source the report attributes a claim to.
 *
 *  `page` is a URL for web citations and a page number for citations into an
 *  uploaded document. `verified` says whether the run actually retrieved that
 *  URL: false means the model produced it without ever fetching it, and absent
 *  means no claim can be made (a document citation has no URL to check, and
 *  runs predating source-ledgering were never checked). */
export interface Citation {
  source: string;
  page: string;
  verified?: boolean;
}

export interface RunMetrics {
  eval_scores?: EvalScores;
  latency_sec?: number;
  citations?: Citation[];
  monitor_diff?: MonitorDiff;
}

export interface Monitor {
  id: string;
  user_id: string;
  workspace_id?: string | null;
  name: string;
  topic: string;
  format: OutputFormat;
  vertical?: Vertical | null;
  vertical_inputs?: Record<string, string>;
  interval_minutes: number;
  enabled: boolean;
  next_run_at: string;
  last_run_id?: string | null;
  last_run_at?: string | null;
  notify_channel?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMonitorInput {
  name: string;
  topic: string;
  format: OutputFormat;
  workspace_id?: string;
  interval_minutes: number;
  enabled: boolean;
  notify_channel?: string | null;
}

/** One recorded LLM call's token usage and cost, filed under the agent that made
 *  it. An agent that ran more than once contributes more than one row, so these
 *  are summed per agent before display. */
export interface RunCost {
  id: string;
  run_id: string;
  agent_name: string;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  created_at: string;
}

export interface RunDetail extends Run {
  logs: LogEntry[];
  research_output: string | null;
  analysis_output: string | null;
  final_output: string | null;
  error_message?: string | null;
  metrics?: RunMetrics;
  /** Optional: a failed run may have spent nothing. */
  costs?: RunCost[];
}

/** Aggregates from `GET /analytics/metrics`.
 *
 *  Counts **completed runs only** — a failed run has no scores to average, so it
 *  is excluded here even though it still cost money. This count and the cost
 *  totals below therefore cover different populations. */
export interface AnalyticsMetrics {
  count: number;
  averages: {
    latency_sec?: number;
    citations?: number;
    accuracy?: number;
    relevance?: number;
    completeness?: number;
    writing_quality?: number;
    overall?: number;
  };
}

export interface AgentCost {
  agent_name: string;
  cost: number;
  input_tokens: number;
  output_tokens: number;
}

/** Aggregates from `GET /analytics/costs`, over **every** run in scope,
 *  including failed ones. */
export interface AnalyticsCosts {
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  per_agent: AgentCost[];
}

export interface LogEntry {
  agent: string;
  message: string;
  ts: string;
}

/** Ingest state of an uploaded PDF. Chunking happens in a background worker
 *  after the upload responds, so a doc is only usable as run context once it
 *  reaches "ready" — at "pending" it has no chunks to retrieve. */
export type DocumentStatus = "pending" | "ready" | "failed";

export interface DocumentState {
  doc_id: string;
  filename: string;
  status: DocumentStatus;
  vertical?: string | null;
  chunk_count?: number | null;
  error_message?: string | null;
}

export type WorkspaceRole = "viewer" | "operator" | "admin";

export interface Workspace {
  id: string;
  name: string;
  owner_id: string;
  /** The *signed-in user's* role in this workspace, not a property of the
   *  workspace itself. Drives which actions the UI offers. */
  role: WorkspaceRole;
}

export interface WorkspaceMember {
  user_id: string;
  role: WorkspaceRole;
}

export const PIPELINE = [
  { id: "input",      label: "Input" },
  { id: "researcher", label: "Researcher" },
  { id: "hitl",       label: "HITL Review" },
  { id: "analyst",    label: "Analyst" },
  { id: "writer",     label: "Writer" },
  { id: "editor",     label: "Editor" },
  { id: "output",     label: "Output" },
] as const;

export const RUN_STATUS_MAP: Record<RunStatus, number> = {
  pending:                    0,
  researching:                1,
  awaiting_hitl:              2,
  awaiting_research_approval: 2,
  analyzing:                  3,
  awaiting_analysis_approval: 4,
  writing:                    5,
  awaiting_final_approval:    6,
  complete:                   7,
  failed:                     -1,
};

/** Factotum's six-state agent model — see docs/design/factotum-design.md. */
export type AgentState = "idle" | "active" | "thinking" | "complete" | "error" | "paused";

export const STATUS_TO_AGENT_STATE: Record<RunStatus, AgentState> = {
  pending:                    "idle",
  researching:                "active",
  awaiting_hitl:              "paused",
  awaiting_research_approval: "paused",
  analyzing:                  "active",
  awaiting_analysis_approval: "paused",
  writing:                    "thinking",
  awaiting_final_approval:    "paused",
  complete:                   "complete",
  failed:                     "error",
};

export const AGENT_STATE_GLYPH: Record<AgentState, string> = {
  idle: "",
  active: "",
  thinking: "◐",
  complete: "✓",
  error: "✕",
  paused: "▮▮",
};

// Text stays neutral (text-content) rather than colored — several agent hues
// can't reach 4.5:1 as text on light surfaces even at their deepened light-mode
// shade. The hue still carries the state via the tint + border; the glyph in
// AGENT_STATE_GLYPH carries it a second way (color is never the only signal).
export const AGENT_STATE_BADGE: Record<AgentState, string> = {
  idle:     "bg-agent-idle/10 border border-agent-idle/40 text-content",
  active:   "bg-agent-active/10 border border-agent-active/40 text-content",
  thinking: "bg-agent-thinking/10 border border-agent-thinking/40 text-content",
  complete: "bg-agent-complete/10 border border-agent-complete/40 text-content",
  error:    "bg-agent-error/10 border border-agent-error/40 text-content",
  paused:   "bg-agent-paused/10 border border-agent-paused/40 text-content",
};

export function statusBadgeClass(status: RunStatus): string {
  return AGENT_STATE_BADGE[STATUS_TO_AGENT_STATE[status]];
}

/**
 * Whether the signed-in user may approve this run's HITL checkpoint.
 *
 * Mirrors `assert_run_access(..., min_role="operator")` in backend/auth.py: a
 * run's own creator always passes, while access granted *via* a workspace needs
 * operator or higher. Anything undeterminable locally — unknown owner, unknown
 * role — resolves to `true` and lets the server decide.
 */
export function canApproveRun(
  run: Pick<Run, "user_id" | "workspace_id">,
  workspaceRole: WorkspaceRole | undefined,
  sessionUserId: string | undefined
): boolean {
  if (!run.workspace_id) return true;
  if (!run.user_id || run.user_id === sessionUserId) return true;
  if (!workspaceRole) return true;
  return workspaceRole === "operator" || workspaceRole === "admin";
}

/**
 * Derives a pipeline node's visual state from the run's overall status.
 * `failedAtStatus` (Run.failed_at_status) pinpoints which stage was active when
 * a "failed" run failed; without it the failure point is unknown and every node
 * stays idle.
 */
export function pipelineNodeState(
  status: RunStatus,
  nodeId: string,
  failedAtStatus?: RunStatus | null
): AgentState {
  const order = PIPELINE.map((n) => n.id) as string[];
  const idx = order.indexOf(nodeId);
  if (status === "failed") {
    if (!failedAtStatus) return "idle";
    const failedIdx = RUN_STATUS_MAP[failedAtStatus] ?? 0;
    if (idx < failedIdx) return "complete";
    if (idx === failedIdx) return "error";
    return "idle";
  }
  const activeIdx = RUN_STATUS_MAP[status] ?? 0;
  if (idx < activeIdx) return "complete";
  if (idx === activeIdx) return STATUS_TO_AGENT_STATE[status];
  return "idle";
}
