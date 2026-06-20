"""
Vertical configuration registry.

Each vertical defines the structured context injected into agent prompts,
the dynamic form fields shown in the frontend, and the output requirements
enforced by the writer/editor.
"""
from typing import TypedDict


# ── Schema types ─────────────────────────────────────────────────────────────

class FieldSchema(TypedDict, total=False):
    label: str
    required: bool
    placeholder: str
    type: str          # "text" | "url" | "select"
    options: list      # for type="select"


class VerticalConfig(TypedDict):
    display_name: str
    description: str
    icon: str                        # emoji shorthand for UI
    input_schema: dict               # {field_key: FieldSchema}
    prompt_focus: str                # injected into researcher / analyst
    output_sections: list            # enforced by writer / editor
    quality_rubric: str              # used by LLM-as-Judge eval
    metric_keys: list                # tracked KPIs per run
    default_format: str              # "report" | "linkedin" | "summary"
    task_type: str                   # "lead_intel" | "research_report"


# ── Registry ─────────────────────────────────────────────────────────────────

VERTICALS: dict[str, VerticalConfig] = {

    "b2b_sales_lead_intel": {
        "display_name": "B2B Sales Lead Intel",
        "description": "Build a prospect dossier — company overview, decision makers, funding, tech stack, and fit score.",
        "icon": "🎯",
        "input_schema": {
            "company_url": {
                "label": "Company URL",
                "required": True,
                "placeholder": "https://acme.com",
                "type": "url",
            },
            "target_role": {
                "label": "Target Buyer Role",
                "required": False,
                "placeholder": "e.g. Head of Engineering, VP Sales",
                "type": "text",
            },
            "our_product": {
                "label": "Your Product / Value Prop",
                "required": False,
                "placeholder": "Brief description of what you sell",
                "type": "text",
            },
        },
        "prompt_focus": (
            "You are building a B2B sales prospect dossier. "
            "Prioritise: company size, funding rounds, tech stack, key decision makers (with LinkedIn if possible), "
            "recent news (hiring, expansion, strategic shifts), and fit signals. "
            "Avoid generic company descriptions — focus on signals that indicate purchase readiness. "
            "Score company fit on a 1–10 scale with clear reasoning."
        ),
        "output_sections": [
            "Company Overview",
            "Key Decision Makers",
            "Recent News & Strategic Signals",
            "Technology Stack",
            "Fit Score & Reasoning",
            "Recommended Outreach Angle",
        ],
        "quality_rubric": (
            "Score on: completeness of decision-maker data (name + title + LinkedIn), "
            "specificity of fit reasoning (tied to real evidence), "
            "recency of news cited (last 3 months preferred), "
            "accuracy of tech stack, and actionability of the outreach angle."
        ),
        "metric_keys": ["fit_score", "decision_makers_found", "news_items_cited"],
        "default_format": "report",
        "task_type": "lead_intel",
    },

    "marketing_competitor_briefs": {
        "display_name": "Marketing Competitor Brief",
        "description": "Analyze a competitor's positioning, content strategy, pricing, and differentiation gaps.",
        "icon": "📊",
        "input_schema": {
            "competitor_name": {
                "label": "Competitor Name",
                "required": True,
                "placeholder": "e.g. Notion, Salesforce, HubSpot",
                "type": "text",
            },
            "our_product": {
                "label": "Your Product / Category",
                "required": False,
                "placeholder": "e.g. AI writing assistant for startups",
                "type": "text",
            },
            "target_market": {
                "label": "Target Market / ICP",
                "required": False,
                "placeholder": "e.g. Series A SaaS founders, SMB marketing teams",
                "type": "text",
            },
        },
        "prompt_focus": (
            "You are producing a competitive intelligence brief for a marketing team. "
            "Prioritise: brand positioning, messaging angles, content pillars, pricing tiers, "
            "target segments, recent campaigns or product launches, and strategic differentiators. "
            "Identify specific gaps the competitor is NOT addressing that could be exploited. "
            "Cite sources for every claim about pricing or positioning."
        ),
        "output_sections": [
            "Competitor Overview",
            "Positioning & Core Messaging",
            "Pricing & Packaging",
            "Content Strategy & Channels",
            "Recent Campaigns & Product Launches",
            "Competitive Gaps & Opportunities",
            "Strategic Recommendations",
        ],
        "quality_rubric": (
            "Score on: accuracy of positioning characterisation, depth of content strategy analysis, "
            "specificity of gap identification, freshness of campaign data, "
            "and actionability of recommendations for the specified target market."
        ),
        "metric_keys": ["campaigns_identified", "pricing_tiers_documented", "gaps_found"],
        "default_format": "report",
        "task_type": "research_report",
    },

    "founder_strategy_briefs": {
        "display_name": "Founder Strategy Brief",
        "description": "Get a strategic landscape analysis — market sizing, competition, timing, and entry points.",
        "icon": "🚀",
        "input_schema": {
            "market_segment": {
                "label": "Market Segment",
                "required": True,
                "placeholder": "e.g. AI-powered legal tech for SMBs",
                "type": "text",
            },
            "stage": {
                "label": "Company Stage",
                "required": False,
                "placeholder": "Select stage",
                "type": "select",
                "options": ["Pre-idea", "Pre-seed", "Seed", "Series A", "Series B+"],
            },
            "key_question": {
                "label": "Key Strategic Question",
                "required": False,
                "placeholder": "e.g. Is now the right time to enter the SMB legal market?",
                "type": "text",
            },
        },
        "prompt_focus": (
            "You are producing a strategic brief for a founder making a high-stakes market decision. "
            "Prioritise: total addressable market sizing (with cited numbers), competitive landscape map, "
            "tailwinds and headwinds, timing indicators, successful analogues in adjacent markets, "
            "and specific entry-point recommendations. "
            "Be direct. Founders need conviction or clear reasons to pivot — not equivocal analysis. "
            "If the answer to their key question is 'no', say so clearly and explain why."
        ),
        "output_sections": [
            "Market Sizing & Opportunity",
            "Competitive Landscape",
            "Tailwinds & Headwinds",
            "Timing Analysis",
            "Strategic Entry Points",
            "Answer to Key Question",
            "Recommended Next Steps",
        ],
        "quality_rubric": (
            "Score on: specificity of market sizing (must include dollar figures with sources), "
            "completeness of competitive mapping (at least 5 players), "
            "clarity of timing reasoning, directness of recommendation, and citation quality."
        ),
        "metric_keys": ["market_size_cited", "competitors_mapped", "entry_points_identified"],
        "default_format": "summary",
        "task_type": "research_report",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_VERTICALS = list(VERTICALS.keys())


def get_vertical(vertical: str | None) -> VerticalConfig | None:
    """Return vertical config by key, or None if unknown / not provided."""
    if not vertical:
        return None
    return VERTICALS.get(vertical)


def build_execution_brief(topic: str, vertical: str | None, vertical_inputs: dict) -> str:
    """
    Compose the execution brief that gets injected into agent prompts.
    If no vertical is configured, returns the plain topic unchanged.
    """
    config = get_vertical(vertical)
    if not config:
        return topic

    inputs_lines = "\n".join(
        f"- **{k.replace('_', ' ').title()}**: {v}"
        for k, v in (vertical_inputs or {}).items()
        if v
    )

    sections = ", ".join(config["output_sections"])

    return (
        f"{topic}\n\n"
        f"**Vertical Playbook**: {config['display_name']}\n\n"
        f"**Structured Context**:\n{inputs_lines}\n\n"
        f"**Research Focus**: {config['prompt_focus']}\n\n"
        f"**Required Output Sections**: {sections}"
    )
