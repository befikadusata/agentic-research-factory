from crewai import Agent, Task

from configs.prompt_loader import get_prompt
from services.llm_router import get_llm
from tools.scraper import batch_scrape_tool, firecrawl_tool
from tools.search import tavily_search_tool


def researcher_agent(tools: list = None, max_iter: int = 2, max_tokens: int = 900) -> Agent:
    if tools is None:
        tools = [tavily_search_tool, firecrawl_tool, batch_scrape_tool]

    prompt = get_prompt("researcher")

    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=tools,
        # max_tokens caps the (token-heavy) synthesis call so a full pass stays
        # under Groq's free 12K tokens/min ceiling — see get_llm docstring. The
        # caller escalates it (and max_iter) on a retry so a re-run after a review
        # FAIL gets more depth than the deliberately-shallow first pass.
        llm=get_llm("researcher", max_tokens=max_tokens),
        verbose=True,
        # Each ReAct iteration re-sends the whole accumulating context, and those
        # tokens count against Groq's rolling free 12K tokens/min window; deeper
        # loops push the final synthesis call to 429. The base of 2 (≈1 search +
        # 1 synthesis) leaves room for a full brief under the ceiling.
        max_iter=max_iter,
    )

def research_task(agent: Agent, topic: str, context_docs: str) -> Task:
    prompt = get_prompt("researcher")
    context_section = f"\n\n**INTERNAL DOCUMENTS**: {context_docs}\n(Use 'search_documents' if this is present)" if context_docs else ""

    return Task(
        description=prompt["task_description"].format(topic=topic, context_section=context_section),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
