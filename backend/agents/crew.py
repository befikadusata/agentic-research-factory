"""
LangGraph supervisor over the single-agent CrewAI nodes.

task_type routing:
  "research_report"  → plan → research → analyse → review → write → edit
                       (a non-PASS review loops back to research)
  "lead_intel"       → lead_intel → lead_review
                       (a non-PASS review loops back to lead_intel)
"""
import operator
import re
from datetime import datetime, timezone
from typing import TypedDict, Literal, Optional, List, Annotated
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from configs.verticals import get_vertical
from logger import logger

class ResearchState(TypedDict):
    topic: str
    vertical: Optional[str]
    vertical_inputs: dict
    task_type: Literal["research_report", "lead_intel"]
    context_docs: str
    workspace_id: str
    collection_name: Optional[str]
    output_format: str
    plan_output: str
    research_output: str
    analysis_output: str
    final_output: str
    review_output: str
    user_feedback: Optional[str]
    retry_count: int
    # Run spend (USD) already persisted to run_costs *before* this graph
    # invocation started — seeded by run_service from the DB so the budget check
    # in route_after_review reflects the whole run, not just the current segment
    # (each segment runs in a fresh process with a fresh token_usages).
    spent_usd: float
    token_usages: Annotated[list, operator.add]
    # Set by run_service when resuming a durably-paused run in a *fresh* process
    # (the InMemorySaver checkpoint doesn't survive Celery's per-task child
    # recycling, so state is rebuilt from the DB and re-entered mid-graph). When
    # present, route_entry sends START straight to this node instead of plan/
    # research. Empty/absent for a normal first invoke.
    _resume_from: Optional[str]


from contextlib import nullcontext
from crewai import Crew, Process
from config import settings
from services.llm_router import resolve_actual_model, reset_actual_model
from utils.agent_output import strip_agent_scaffolding
from utils.context import compact_text
from utils.cost_tracker import reset_side_costs, take_side_costs
from utils.langfuse_utils import get_langfuse
from utils.pricing import calculate_cost


def _researcher_budget(retry_count: int) -> tuple[int, int]:
    """(max_iter, max_tokens) for the researcher, escalating on retry.

    The first pass (retry_count 0) keeps the free-tier-tuned base budget. Each
    retry — which only happens after the reviewer FAILed the prior pass — gets one
    more ReAct iteration and a larger synthesis reservation, so it can act on the
    feedback instead of repeating (and re-billing) the undersized pass that already
    failed. retry_count is bounded by the route's retry cap of 3, so the escalation
    can't run away.
    """
    n = max(retry_count, 0)
    max_iter = settings.RESEARCHER_MAX_ITER + n
    max_tokens = settings.RESEARCHER_MAX_TOKENS + settings.RESEARCHER_RETRY_TOKEN_STEP * n
    return max_iter, max_tokens

def _run_crew_node(agents_list, tasks_list, state: ResearchState, config: RunnableConfig, result_key: str, agent_key: str) -> dict:
    lf = get_langfuse()

    # step_callback is a live Python function, not state — it can't go through
    # ResearchState because the checkpointer serializes every state update
    # (functions aren't msgpack-serializable). It travels via config instead,
    # which is per-call and never persisted.
    cb = (config.get("configurable") or {}).get("step_callback")
    crew = Crew(
        agents=agents_list,
        tasks=tasks_list,
        process=Process.sequential,
        verbose=True,
        step_callback=cb,
    )

    logger.info("crew_node_start", node=result_key)
    # Clear the captured served-model so resolve_actual_model() below reads only
    # what *this* kickoff used (the primary, or a fallback if it spilled).
    reset_actual_model()
    # Clear the side-cost buffer so we drain only the direct litellm calls (the
    # RAG query_rewriter) fired during *this* node's kickoff.
    reset_side_costs()
    # Langfuse v4's client dropped the old .trace()/.span() object model in
    # favor of an OTEL-based context manager (start_as_current_observation);
    # nullcontext() keeps `span` as None so the tracing calls below can be
    # unconditional instead of duplicating the kickoff/logging block per branch.
    span_cm = (
        lf.start_as_current_observation(name=f"crew_node_{result_key}", as_type="span")
        if lf else nullcontext()
    )
    with span_cm as span:
        try:
            result = crew.kickoff()
        except Exception:
            logger.exception("crew_node_failed", node=result_key)
            if span is not None:
                span.update(level="ERROR", status_message="crew_kickoff_failed")
            raise
        usage = result.token_usage
        # Model that actually served this call — the configured primary, or the
        # fallback slug if litellm spilled over during a provider outage. Pricing
        # keys off this, so a fallback leg is costed correctly instead of being
        # priced against a primary that never ran.
        model = resolve_actual_model(agent_key)
        prompt_tokens     = usage.prompt_tokens     if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        if span is not None:
            # Correlate the Langfuse trace with the DB run and its cost rows: the
            # run id (the graph thread_id) plus the exact model / token / cost that
            # run_service also writes to run_costs.
            rid = (config.get("configurable") or {}).get("thread_id")
            span.update(
                output=str(result),
                model=model,
                metadata={"run_id": rid, "agent": agent_key},
                usage_details={"input": prompt_tokens, "output": completion_tokens},
                cost_details={"total": calculate_cost(model, prompt_tokens, completion_tokens)},
            )

    logger.info("crew_node_complete", node=result_key)
    # Fold in any direct-litellm side calls (the RAG query_rewriter) made during
    # this kickoff so their cost is persisted through the normal token path
    # instead of vanishing.
    node_usage = {
        "agent_name":        result_key,
        "model":             model,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    # Strip here rather than at persistence: this is the one place every node's
    # output becomes state, so the cleaned text is what the reviewer, evaluator
    # and citation extractor see downstream — not just what the DB stores.
    return {
        "token_usages": [node_usage, *take_side_costs()],
        result_key: strip_agent_scaffolding(str(result)),
    }


def node_plan(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.strategist import strategist_agent, planning_task
    agent = strategist_agent()
    task = planning_task(agent, state["topic"])
    return _run_crew_node([agent], [task], state, config, "plan_output", "strategist")


def node_research(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.researcher import researcher_agent, research_task
    from tools.search import tavily_search_tool
    from tools.scraper import firecrawl_tool, batch_scrape_tool
    from tools.rag import RAGTool

    collection = state.get("collection_name") or "default_workspace"
    custom_rag = RAGTool(collection_name=collection, vertical=state.get("vertical"))

    # web_search + RAG only. Each tool's JSON schema is re-sent on every ReAct
    # iteration, so the 2 scraper tools (optional in this stack) inflated every
    # researcher call past Groq's free 12K tokens/min. Dropping them keeps a full
    # pass under the ceiling.
    tools = [tavily_search_tool, custom_rag]

    # Deeper budget on a retry: a re-run after a review FAIL gets more iterations
    # and a larger synthesis reservation than the shallow first pass.
    max_iter, max_tokens = _researcher_budget(state.get("retry_count", 0))
    agent = researcher_agent(tools=tools, max_iter=max_iter, max_tokens=max_tokens)

    # Enrich topic with plan if available. The plan is re-sent on every ReAct
    # iteration, so cap it — the full plan pushed each researcher call over Groq's
    # free 12K tokens/min ceiling. Head+tail keeps the intent up front and any
    # closing constraints, rather than a blind head clip.
    topic = state["topic"]
    if state.get("plan_output"):
        plan = compact_text(state["plan_output"], 1200)
        topic = f"{topic}\n\n**RESEARCH PLAN**:\n{plan}"

    if state.get("user_feedback"):
        topic = f"{topic}\n\n**USER FEEDBACK**:\n{state['user_feedback']}"

    # If we are retrying (the reviewer's verdict was anything but PASS), fold the
    # audit back in as retry feedback — read from the verdict field, not a bare
    # "FAIL" substring. Bound it so a verbose audit can't balloon the retry prompt
    # on the rate-limited retry path.
    if state.get("review_output") and review_verdict(state["review_output"]) != "PASS":
        feedback = compact_text(state["review_output"], settings.CONTEXT_MAX_CHARS)
        topic = f"{topic}\n\n**RETRY FEEDBACK**:\n{feedback}"

    task = research_task(agent, topic, state.get("context_docs", ""))
    return _run_crew_node([agent], [task], state, config, "research_output", "researcher")


def node_lead_intel(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.lead_intel import lead_intel_agent, lead_intel_task
    agent = lead_intel_agent()
    
    topic = state["topic"]
    feedback = state.get("review_output") or state.get("user_feedback")
    if feedback:
        topic = f"{topic}\n\n**REQUIRED CORRECTIONS FROM REVIEW**:\n{compact_text(feedback, 2000)}"
        
    task = lead_intel_task(agent, topic, state.get("vertical_inputs"))
    return _run_crew_node([agent], [task], state, config, "final_output", "lead_intel")


def lead_intel_contract_failures(
    output: str,
    target_role: str = "",
    current_year: int | None = None,
) -> list[str]:
    """Deterministic release-gate checks that the LLM reviewer cannot waive."""
    lowered = (output or "").lower()
    failures = []
    for heading, label in (
        ("target buyer", "Target Buyer section"),
        ("purchase-readiness", "Purchase-Readiness Evidence section"),
        ("source evidence ledger", "Source Evidence Ledger"),
    ):
        if heading not in lowered:
            failures.append(f"Missing {label}")
    if target_role and target_role.lower() not in lowered and "not confidently identified" not in lowered:
        failures.append(f"Requested buyer role '{target_role}' is not addressed")
    buyer_match = re.search(
        r"#{1,6}\s+Target Buyer[^\n]*\n(.*?)(?=\n#{1,6}\s|\Z)",
        output or "",
        re.IGNORECASE | re.DOTALL,
    )
    buyer_section = buyer_match.group(1) if buyer_match else ""
    if not re.search(r"https?://", buyer_section):
        failures.append("No source URL supports current personnel claims")
    source_years = [int(year) for year in re.findall(r"\b(20\d{2})\b", buyer_section)]
    if not source_years:
        failures.append("No publication/update date supports current personnel claims")
    else:
        current_year = current_year or datetime.now(timezone.utc).year
        if max(source_years) < current_year - 1:
            failures.append("Target-buyer title is supported only by stale sources")
    return failures


def node_lead_review(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.reviewer import reviewer_agent, review_task

    vertical_config = get_vertical(state.get("vertical"))
    rubric = vertical_config["quality_rubric"] if vertical_config else "Verify buyer identity, freshness, sources, and purchase readiness."
    target_role = str((state.get("vertical_inputs") or {}).get("target_role") or "")
    failures = lead_intel_contract_failures(state.get("final_output", ""), target_role)
    agent = reviewer_agent()
    task = review_task(
        agent,
        state["topic"],
        f"LEAD-INTEL REPORT:\n{state.get('final_output', '')}",
        rubric,
    )
    result = _run_crew_node([agent], [task], state, config, "review_output", "reviewer")
    review = result.get("review_output", "")
    if failures:
        findings = "\n".join(f"- {failure}" for failure in failures)
        review = f"VERDICT: FAIL\n\n### Quality Audit: FAIL\n\n#### Critical Findings:\n{findings}\n\n{review}"
    result["review_output"] = review
    result["retry_count"] = state.get("retry_count", 0) + 1
    return result


def node_analyse(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.analyst import analyst_agent, analysis_task
    agent = analyst_agent()
    
    topic = state["topic"]
    if state.get("plan_output"):
        topic = f"{topic}\n\n**RESEARCH PLAN**:\n{state['plan_output']}"

    if state.get("user_feedback"):
        topic = f"{topic}\n\n**USER FEEDBACK**:\n{state['user_feedback']}"
    
    task = analysis_task(agent, topic)
    task.context = []
    # Reference material for the analysis — bound it so an oversized research brief
    # can't balloon this prompt; normally under budget and unchanged.
    research = compact_text(state["research_output"], settings.CONTEXT_MAX_CHARS)
    task.description = f"Research summary:\n{research}\n\n" + task.description
    return _run_crew_node([agent], [task], state, config, "analysis_output", "analyst")


def node_review(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.reviewer import reviewer_agent, review_task
    
    vertical_config = get_vertical(state.get("vertical"))
    rubric = vertical_config["quality_rubric"] if vertical_config else "Ensure accuracy, depth, and citation completeness."
    
    agent = reviewer_agent()
    current_work = f"RESEARCH:\n{state['research_output']}\n\nANALYSIS:\n{state['analysis_output']}"
    task = review_task(agent, state["topic"], current_work, rubric)
    
    res = _run_crew_node([agent], [task], state, config, "review_output", "reviewer")
    res["retry_count"] = state.get("retry_count", 0) + 1
    return res


def node_write(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.writer import writer_agent, write_task
    agent = writer_agent()
    task = write_task(agent, state["topic"], state["output_format"])
    # Prior work is reference the writer draws from (not the deliverable itself),
    # so bound it. This hop is post-review, so trimming can't trigger a review
    # retry; normally under budget and passed through unchanged.
    prior = state.get("analysis_output") or state.get("research_output", "")
    prior = compact_text(prior, settings.CONTEXT_MAX_CHARS)
    task.description = f"Prior work:\n{prior}\n\n" + task.description
    if state.get("user_feedback"):
        task.description += f"\n\n**USER FEEDBACK**:\n{state['user_feedback']}"
    return _run_crew_node([agent], [task], state, config, "final_output", "writer")


def node_edit(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.editor import editor_agent, edit_task
    agent = editor_agent()
    task = edit_task(agent, state["topic"])
    task.description = f"Draft:\n{state['final_output']}\n\n" + task.description
    return _run_crew_node([agent], [task], state, config, "final_output", "editor")


def route_after_research(state: ResearchState) -> str:
    return "analyse"


def route_entry(state: ResearchState) -> str:
    # Runs on the initial invoke() of a fresh thread. Two cases:
    #  1. Same-process resume after an interrupt (invoke(None, config)) continues
    #     from the paused node directly and never re-enters routing from START.
    #  2. Cross-process durable resume: run_service rebuilds state from the DB in
    #     a brand-new worker child (the in-memory checkpoint is gone) and sets
    #     `_resume_from` to re-enter mid-graph. interrupt_before still fires on
    #     that node, so the first invoke pauses before it and invoke(None) runs it.
    resume_from = state.get("_resume_from")
    if resume_from:
        return resume_from
    if state["task_type"] == "lead_intel":
        return "lead_intel"
    if state["task_type"] == "research_report":
        return "plan"
    return "research"


# The reviewer emits a machine-readable verdict field ("VERDICT: PASS|FAIL") as
# the first line of its report; failing that, the human-readable "Quality Audit:"
# header. We read the verdict *only* from that dedicated field — never a bare
# substring scan of the prose, where "passes accuracy but fails completeness"
# would false-match "PASS" and skip a warranted retry.
_VERDICT_RE = re.compile(r"VERDICT\s*[:\-]\s*\[?\s*(PASS|FAIL)", re.IGNORECASE)
_AUDIT_HEADER_RE = re.compile(r"Quality\s+Audit\s*[:\-]\s*\[?\s*(PASS|FAIL)", re.IGNORECASE)


def review_verdict(review_output: str) -> Optional[str]:
    """Extract the reviewer's binary verdict from its labeled field.

    Returns "PASS"/"FAIL", or None if no verdict field is present/parseable
    (an unparseable review is treated as not-a-pass by callers, so a malformed
    audit spends a retry rather than being rubber-stamped through).
    """
    if not review_output:
        return None
    m = _VERDICT_RE.search(review_output) or _AUDIT_HEADER_RE.search(review_output)
    return m.group(1).upper() if m else None


def _run_spend_usd(state: ResearchState) -> float:
    """Run spend so far: the cost persisted before this graph invocation
    (spent_usd, seeded from run_costs) plus the in-flight segment's token_usages."""
    spent = float(state.get("spent_usd", 0.0) or 0.0)
    for u in state.get("token_usages", []):
        spent += calculate_cost(
            u.get("model", ""), u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        )
    return spent


def _over_budget(state: ResearchState) -> bool:
    """True once the run's accumulated LLM spend reaches RUN_COST_CEILING_USD.
    Disabled (always False) when the ceiling is None or <= 0 — the free-tier
    default prices to ~$0, so this only ever bites a paid-key deployment."""
    ceiling = settings.RUN_COST_CEILING_USD
    if not ceiling or ceiling <= 0:
        return False
    spent = _run_spend_usd(state)
    if spent >= ceiling:
        logger.warning(
            "run_cost_ceiling_reached",
            spent_usd=round(spent, 4),
            ceiling_usd=ceiling,
            retry_count=state.get("retry_count", 0),
        )
        return True
    return False


def route_after_review(state: ResearchState) -> str:
    review_output = state.get("review_output", "")
    if review_verdict(review_output) == "PASS":
        return "write"

    # FAIL or unparseable: retry from research while BOTH the retry budget and the
    # cost ceiling allow it. Once the run's spend ceiling is reached, ship what we
    # have rather than burning the full retry allowance regardless of spend.
    if review_output and state.get("retry_count", 0) < 3 and not _over_budget(state):
        return "research"

    return "write"


def route_after_lead_review(state: ResearchState) -> str:
    if review_verdict(state.get("review_output", "")) == "PASS":
        return "end"
    if state.get("retry_count", 0) < 2 and not _over_budget(state):
        return "lead_intel"
    return "end"


from langgraph.checkpoint.memory import InMemorySaver

# One process-lifetime checkpointer shared by every run; runs are isolated from
# each other by thread_id (the run id), and run_service purges a run's entries
# via `supervisor.checkpointer.delete_thread(run_id)` once the run finishes.
checkpointer = InMemorySaver()


def build_graph() -> StateGraph:
    g = StateGraph(ResearchState)

    g.add_node("plan",       node_plan)
    g.add_node("research",   node_research)
    g.add_node("lead_intel", node_lead_intel)
    g.add_node("lead_review", node_lead_review)
    g.add_node("analyse",    node_analyse)
    g.add_node("review",     node_review)
    g.add_node("write",      node_write)
    g.add_node("edit",       node_edit)

    g.add_conditional_edges(
        START,
        route_entry,
        {"lead_intel": "lead_intel", "plan": "plan", "research": "research", "analyse": "analyse", "write": "write"},
    )
    
    g.add_edge("plan", "research")
    
    g.add_conditional_edges(
        "research",
        route_after_research,
        {"analyse": "analyse", "write": "write"},
    )
    
    g.add_edge("analyse", "review")
    
    g.add_conditional_edges(
        "review",
        route_after_review,
        {"research": "research", "write": "write"},
    )
    
    g.add_edge("lead_intel", "lead_review")
    g.add_conditional_edges(
        "lead_review",
        route_after_lead_review,
        {"lead_intel": "lead_intel", "end": END},
    )
    g.add_edge("write",      "edit")
    g.add_edge("edit",       END)

    # interrupt_before is what makes the HITL gates real: the compiled graph stops
    # before "analyse" and before "write" and returns control to run_service, which
    # only resumes it (via .invoke(None, config)) after a human approves the prior
    # stage. Without it, .invoke() runs the whole graph to END in one call.
    return g.compile(checkpointer=checkpointer, interrupt_before=["analyse", "write"])


# Compiled graph — import and call .invoke(state) from run_service
supervisor = build_graph()
