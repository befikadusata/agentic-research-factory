from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_model

def strategist_agent() -> Agent:
    prompt = get_prompt("strategist")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        llm=get_model("strategist"),
        verbose=True,
    )

def planning_task(agent: Agent, topic: str) -> Task:
    prompt = get_prompt("strategist")
    return Task(
        description=prompt["task_description"].format(topic=topic),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
