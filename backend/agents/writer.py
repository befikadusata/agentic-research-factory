from crewai import Agent, Task
from configs.prompt_loader import get_prompt
from services.llm_router import get_llm

def writer_agent() -> Agent:
    prompt = get_prompt("writer")
    return Agent(
        role=prompt["role"],
        goal=prompt["goal"],
        backstory=prompt["backstory"],
        tools=[],
        llm=get_llm("writer"),
        verbose=True,
        max_iter=3,
    )

def write_task(agent: Agent, topic: str, output_format: str) -> Task:
    prompt = get_prompt("writer")
    format_instructions = prompt["format_instructions"]
    instructions = format_instructions.get(output_format, format_instructions["report"])

    # Extract vertical-specific output sections if present
    vertical_section = ""
    if "**Required Output Sections**:" in topic:
        vertical_section = prompt["vertical_section"]

    return Task(
        description=prompt["task_description"].format(
            topic=topic,
            output_format=output_format,
            instructions=instructions,
            vertical_section=vertical_section,
        ),
        expected_output=prompt["expected_output"].format(output_format=output_format),
        agent=agent,
    )
