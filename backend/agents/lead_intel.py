from datetime import UTC, datetime

from crewai import Agent, Task

from configs.prompt_loader import get_prompt
from services.llm_router import get_llm
from tools.scraper import firecrawl_tool
from tools.search import tavily_search_tool


def lead_intel_agent() -> Agent:
    prompt = get_prompt("lead_intel")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[tavily_search_tool, firecrawl_tool],
        # Cap the completion (pipeline-wide token invariant); generous, since this
        # single agent produces the whole lead dossier deliverable.
        llm=get_llm("lead_intel", max_tokens=1800),
        verbose=True,
        max_iter=10,
    )


def _buyer_search_terms(target_role: str) -> str:
    role = (target_role or "").strip()
    lowered = role.lower()
    if any(term in lowered for term in ("ciso", "security", "infosec")):
        return f'"{role or "CISO"}" OR "information security" OR risk OR trust OR privacy'
    if any(term in lowered for term in ("privacy", "data protection")):
        return f'"{role}" OR privacy OR "data protection" OR trust'
    return f'"{role or "relevant decision maker"}"'


def lead_intel_task(
    agent: Agent,
    execution_brief: str,
    vertical_inputs: dict | None = None,
    current_date: str | None = None,
) -> Task:
    prompt = get_prompt("lead_intel")
    return Task(
        description=build_lead_intel_description(execution_brief, vertical_inputs, current_date),
        expected_output=prompt["expected_output"],
        agent=agent,
    )


def build_lead_intel_description(
    execution_brief: str,
    vertical_inputs: dict | None = None,
    current_date: str | None = None,
) -> str:
    prompt = get_prompt("lead_intel")
    inputs = vertical_inputs or {}
    target_role = str(inputs.get("target_role") or "relevant decision maker")
    our_product = str(inputs.get("our_product") or "not provided; state assumptions explicitly")
    current_date = current_date or datetime.now(UTC).date().isoformat()
    current_year = int(current_date[:4])

    vertical_section = ""
    if "**Vertical Playbook**:" in execution_brief:
        vertical_section = prompt["vertical_section"]
    company_url = str(inputs.get("company_url") or execution_brief.splitlines()[0]).strip()

    return prompt["task_description"].format(
        company_url=company_url,
        execution_brief=execution_brief,
        vertical_section=vertical_section,
        current_date=current_date,
        recent_period=f"{current_year - 1} {current_year}",
        target_role=target_role,
        buyer_search_terms=_buyer_search_terms(target_role),
        our_product=our_product,
    )
