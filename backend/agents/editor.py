from crewai import Agent, Task
from config import settings

def editor_agent() -> Agent:
    return Agent(
        role="Chief Editorial Officer",
        goal="Perform a final, surgical polish of the content to ensure it is flawless, impactful, and fully cited.",
        backstory=(
            "You are a legendary editor known for turning good drafts into great ones. "
            "You have an obsession with brevity and impact. You delete filler words without mercy. "
            "You verify that every H1 and H2 is punchy and that the document flow is irresistible. "
            "You are also a stickler for citation consistency—if a source is in the research summary "
            "but missing from the draft, you find the right place for it."
        ),
        tools=[],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=3,
    )

def edit_task(agent: Agent, topic: str) -> Task:
    # Extract vertical-specific output sections if present
    vertical_section = ""
    if "**Required Output Sections**:" in topic:
        vertical_section = (
            "\n\n**PLAYBOOK VERIFICATION**\n"
            "Cross-check the draft against the Required Output Sections in the topic brief. "
            "If a required section is thin or missing, expand or add it using data from the research summary."
        )

    return Task(
        description=f"""
Perform the final edit for the document about: **{topic}**

Think step-by-step:
1. **Structural Audit**: Does the document follow the requested format and vertical mandates?
2. **Fact & Citation Check**: Are all claims supported? Are links formatted correctly in Markdown?
3. **Tone & Hook**: Is the opening strong? Is the voice consistent?
4. **Brevity**: Can any sentence be shorter? Can passive voice be made active?

Rules:
- Output the COMPLETE final document.
- Use only Markdown.
- No meta-commentary (e.g. "Here is the edited version").
{vertical_section}
""",
        expected_output="The final, definitive version of the document in polished Markdown.",
        agent=agent,
    )
