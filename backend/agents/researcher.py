from crewai import Agent, Task
from tools.search import tavily_search_tool
from tools.scraper import firecrawl_tool, batch_scrape_tool
from configs.prompt_loader import get_prompt
from services.llm_router import get_model

def researcher_agent(tools: list = None) -> Agent:
    if tools is None:
        tools = [tavily_search_tool, firecrawl_tool, batch_scrape_tool]
    
    prompt = get_prompt("researcher")
    
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=tools,
        llm=get_model("researcher"),
        verbose=True,
        max_iter=10,
    )

def research_task(agent: Agent, topic: str, context_docs: str) -> Task:
    prompt = get_prompt("researcher")
    context_section = f"\n\n**INTERNAL DOCUMENTS**: {context_docs}\n(Use 'search_documents' if this is present)" if context_docs else ""

    return Task(
        description=prompt["task_description"].format(topic=topic, context_section=context_section),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
