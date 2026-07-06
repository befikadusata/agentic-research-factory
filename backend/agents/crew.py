"""
LangGraph Supervisor — replaces the sequential CrewAI crew.

task_type routing:
  "research_report"  → Researcher → Analyst → Writer → Editor
  "lead_intel"       → LeadIntel agent only
"""
import operator
from typing import TypedDict, Literal, Optional, List, Annotated
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from configs.verticals import get_vertical
from logger import logger

class ResearchState(TypedDict):
    topic: str
    vertical: Optional[str]
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
    token_usages: Annotated[list, operator.add]


# ── node helpers ────────────────────────────────────────────────────────────

from contextlib import nullcontext
from crewai import Crew, Process
from services.llm_router import get_model
from utils.langfuse_utils import get_langfuse

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
        if span is not None:
            span.update(output=str(result))

    logger.info("crew_node_complete", node=result_key)
    usage = result.token_usage
    return {
        result_key: str(result),
        "token_usages": [{
            "agent_name":        result_key,
            # Model actually used for this call, so run_service can look up
            # real per-model pricing instead of hardcoding cost to $0 (§4.1).
            "model":             get_model(agent_key),
            "prompt_tokens":     (usage.prompt_tokens     if usage else 0),
            "completion_tokens": (usage.completion_tokens if usage else 0),
        }],
    }


# ── nodes ────────────────────────────────────────────────────────────────────

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

    # Workspace-based RAG tool
    collection = state.get("collection_name") or "default_workspace"
    custom_rag = RAGTool(collection_name=collection, vertical=state.get("vertical"))

    tools = [tavily_search_tool, custom_rag, firecrawl_tool, batch_scrape_tool]

    agent = researcher_agent(tools=tools)
    
    # Enrich topic with plan if available
    topic = state["topic"]
    if state.get("plan_output"):
        topic = f"{topic}\n\n**RESEARCH PLAN**:\n{state['plan_output']}"
    
    # NEW: Add feedback if available
    if state.get("user_feedback"):
        topic = f"{topic}\n\n**USER FEEDBACK**:\n{state['user_feedback']}"

    # If we are retrying, add feedback
    if state.get("review_output") and "FAIL" in state["review_output"]:
        topic = f"{topic}\n\n**RETRY FEEDBACK**:\n{state['review_output']}"

    task = research_task(agent, topic, state.get("context_docs", ""))
    return _run_crew_node([agent], [task], state, config, "research_output", "researcher")


def node_lead_intel(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.lead_intel import lead_intel_agent, lead_intel_task
    agent = lead_intel_agent()
    
    topic = state["topic"]
    # NEW: Add feedback if available
    if state.get("user_feedback"):
        topic = f"{topic}\n\n**USER FEEDBACK**:\n{state['user_feedback']}"
        
    task = lead_intel_task(agent, topic)
    return _run_crew_node([agent], [task], state, config, "final_output", "lead_intel")


def node_analyse(state: ResearchState, config: RunnableConfig) -> dict:
    from agents.analyst import analyst_agent, analysis_task
    agent = analyst_agent()
    
    topic = state["topic"]
    if state.get("plan_output"):
        topic = f"{topic}\n\n**RESEARCH PLAN**:\n{state['plan_output']}"
        
    # NEW: Add feedback if available
    if state.get("user_feedback"):
        topic = f"{topic}\n\n**USER FEEDBACK**:\n{state['user_feedback']}"
    
    task = analysis_task(agent, topic)
    task.context = []
    task.description = f"Research summary:\n{state['research_output']}\n\n" + task.description
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
    prior = state.get("analysis_output") or state.get("research_output", "")
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


# ── routing ──────────────────────────────────────────────────────────────────

def route_after_research(state: ResearchState) -> str:
    return "analyse"


def route_entry(state: ResearchState) -> str:
    # This only runs once, for the initial invoke() of a fresh thread — resuming
    # after an interrupt (invoke(None, config)) continues from the paused node
    # directly and never re-enters routing from START. It used to also sniff
    # analysis_output/research_output to fake a "resume" by re-entering from
    # START with hand-built state; that's now handled by the checkpointer.
    if state["task_type"] == "lead_intel":
        return "lead_intel"
    if state["task_type"] == "research_report":
        return "plan"
    return "research"


def route_after_review(state: ResearchState) -> str:
    # If PASS, go to write
    if "PASS" in state.get("review_output", ""):
        return "write"
    
    # If FAIL and we haven't hit the retry limit, go back to research
    # Only retry if we actually have review output (indicating a failed review)
    if state.get("review_output") and state.get("retry_count", 0) < 3:
        return "research"
    
    # Otherwise, proceed anyway
    return "write"


# ── graph ────────────────────────────────────────────────────────────────────

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
    
    g.add_edge("lead_intel", END)
    g.add_edge("write",      "edit")
    g.add_edge("edit",       END)

    # interrupt_before makes these pauses real: the compiled graph stops execution
    # before "analyse" and before "write" and returns control to run_service, which
    # only resumes it (via .invoke(None, config)) after a human approves the prior
    # stage. Without this, .invoke() runs the whole graph to END in one call and the
    # HITL gates in run_service were just re-invoking it with hand-rolled state,
    # never actually pausing anything.
    return g.compile(checkpointer=checkpointer, interrupt_before=["analyse", "write"])


# Compiled graph — import and call .invoke(state) from run_service
supervisor = build_graph()
