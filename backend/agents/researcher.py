from crewai import Agent, Task
from tools.search import tavily_search_tool
from tools.scraper import firecrawl_tool, batch_scrape_tool
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def researcher_agent(tools: list = None) -> Agent:
    if tools is None:
        tools = [tavily_search_tool, firecrawl_tool, batch_scrape_tool]
    
    prompt = get_prompt("researcher")
    
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=tools,
        # max_tokens caps the (token-heavy) synthesis call so a full pass stays
        # under Groq's free 12K tokens/min ceiling — see get_llm docstring.
        llm=get_llm("researcher", max_tokens=900),
        verbose=True,
        # Capped at 2 (was 10): each ReAct iteration re-sends the whole
        # accumulating context AND its actual tokens count against Groq's rolling
        # free 12K tokens/min window. Deeper loops pushed the accumulated usage so
        # high that the final synthesis call 429'd. 2 iterations (≈1 search + 1
        # synthesis) leaves room for a full brief under the ceiling.
        max_iter=2,
    )

def research_task(agent: Agent, topic: str, context_docs: str) -> Task:
    prompt = get_prompt("researcher")
    context_section = f"\n\n**INTERNAL DOCUMENTS**: {context_docs}\n(Use 'search_documents' if this is present)" if context_docs else ""

    return Task(
        description=prompt["task_description"].format(topic=topic, context_section=context_section),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
