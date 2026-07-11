from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def editor_agent() -> Agent:
    prompt = get_prompt("editor")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        llm=get_llm("editor"),
        verbose=True,
        max_iter=3,
    )

def edit_task(agent: Agent, topic: str) -> Task:
    prompt = get_prompt("editor")

    # Extract vertical-specific output sections if present
    vertical_section = ""
    if "**Required Output Sections**:" in topic:
        vertical_section = prompt["vertical_section"]

    return Task(
        description=prompt["task_description"].format(topic=topic, vertical_section=vertical_section),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
