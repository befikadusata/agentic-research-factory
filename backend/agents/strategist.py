from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def strategist_agent() -> Agent:
    prompt = get_prompt("strategist")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        # Every agent caps its completion so no single call can breach the
        # free-tier 12K-tok/min ceiling — and, because each stage's output is
        # bounded, the uncapped upstream text every downstream node re-feeds is
        # bounded too. The plan is short, so a tight cap suffices here.
        llm=get_llm("strategist", max_tokens=700),
        verbose=True,
    )

def planning_task(agent: Agent, topic: str) -> Task:
    prompt = get_prompt("strategist")
    return Task(
        description=prompt["task_description"].format(topic=topic),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
