from crewai import Agent, Task
from tools.search import tavily_search_tool
from tools.scraper import firecrawl_tool
from configs.prompt_loader import get_prompt
from services.llm_router import get_model


def lead_intel_agent() -> Agent:
    prompt = get_prompt("lead_intel")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[tavily_search_tool, firecrawl_tool],
        llm=get_model("lead_intel"),
        verbose=True,
        max_iter=10,
    )


def lead_intel_task(agent: Agent, company_url: str) -> Task:
    prompt = get_prompt("lead_intel")

    # Extract vertical playbook from topic if present
    vertical_section = ""
    if "**Vertical Playbook**:" in company_url:
        vertical_section = prompt["vertical_section"]

    return Task(
        description=prompt["task_description"].format(company_url=company_url, vertical_section=vertical_section),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
