from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def reviewer_agent() -> Agent:
    prompt = get_prompt("reviewer")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        # Cap the completion (pipeline-wide token invariant); an audit report is
        # concise, so a tight cap suffices.
        llm=get_llm("reviewer", max_tokens=800),
        verbose=True,
    )

def review_task(agent: Agent, topic: str, current_output: str, rubric: str) -> Task:
    prompt = get_prompt("reviewer")
    return Task(
        description=prompt["task_description"].format(topic=topic, rubric=rubric, current_output=current_output),
        expected_output=prompt["expected_output"],
        agent=agent,
    )
