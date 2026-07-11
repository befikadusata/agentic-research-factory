from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def analyst_agent() -> Agent:
    prompt = get_prompt("analyst")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        llm=get_llm("analyst"),
        verbose=True,
        max_iter=5,
    )

def analysis_task(agent: Agent, topic: str) -> Task:
    prompt = get_prompt("analyst")

    # Extract vertical playbook from topic if present
    vertical_section = ""
    if "**Vertical Playbook**:" in topic:
        vertical_section = prompt["vertical_section"]

    return Task(
        description=prompt["task_description"].format(topic=topic, vertical_section=vertical_section),
        expected_output=prompt["expected_output"],
        agent=agent,
        context=[],
    )
