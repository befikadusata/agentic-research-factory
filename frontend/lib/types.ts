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
  icon: string;
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
    icon: "🎯",
    defaultFormat: "report",
    accentClass: "text-violet-400 bg-violet-950/40 border-violet-900/60",
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
    icon: "📊",
    defaultFormat: "report",
    accentClass: "text-blue-400 bg-blue-950/40 border-blue-900/60",
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
    icon: "🚀",
    defaultFormat: "summary",
    accentClass: "text-emerald-400 bg-emerald-950/40 border-emerald-900/60",
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
  topic: string;
  format: OutputFormat;
  status: RunStatus;
  vertical?: Vertical | null;
  vertical_inputs?: Record<string, string>;
  created_at: string;
}

export interface RunDetail extends Run {
  logs: LogEntry[];
  research_output: string | null;
  analysis_output: string | null;
  final_output: string | null;
  error_message?: string | null;
}

export interface LogEntry {
  agent: string;
  message: string;
  ts: string;
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

export const STATUS_COLORS: Record<RunStatus, string> = {
  pending:                    "bg-status-pending-bg text-status-pending-text",
  researching:                "bg-status-researching-bg text-status-researching-text",
  awaiting_hitl:              "bg-status-awaiting_hitl-bg text-status-awaiting_hitl-text",
  awaiting_research_approval: "bg-status-awaiting_hitl-bg text-status-awaiting_hitl-text",
  analyzing:                  "bg-status-researching-bg text-status-researching-text",
  awaiting_analysis_approval: "bg-status-awaiting_hitl-bg text-status-awaiting_hitl-text",
  writing:                    "bg-status-writing-bg text-status-writing-text",
  awaiting_final_approval:    "bg-status-awaiting_hitl-bg text-status-awaiting_hitl-text",
  complete:                   "bg-status-complete-bg text-status-complete-text",
  failed:                     "bg-status-failed-bg text-status-failed-text",
};

