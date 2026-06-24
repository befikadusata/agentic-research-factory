from crewai import Agent, Task
from services.llm_router import get_model

def analyst_agent() -> Agent:
    return Agent(
        role="Strategic Insights Analyst",
        goal="Synthesize raw research into high-impact strategic insights, identifying the 'non-obvious' patterns and opportunities.",
        backstory=(
            "You are an elite analyst with experience at a top-three global strategy firm. "
            "You excel at connecting disparate data points to form a coherent strategic narrative. "
            "You don't just summarize; you interpret. You understand market dynamics, unit economics, "
            "and competitive positioning. Your trademark is the 'so what?'—translating facts into "
            "direct strategic implications for leadership."
        ),
        tools=[],
        llm=get_model("analyst"),
        verbose=True,
        max_iter=5,
    )

def analysis_task(agent: Agent, topic: str) -> Task:
    # Extract vertical playbook from topic if present
    vertical_section = ""
    if "**Vertical Playbook**:" in topic:
        vertical_section = (
            "\n\n**VERTICAL PLAYBOOK ENFORCEMENT**\n"
            "Apply the specific strategic lenses and 'Research Focus' from the playbook. "
            "Address any required metrics (e.g. Fit Score, TAM) with rigorous logic."
        )

    return Task(
        description=f"""
Perform a strategic synthesis for: **{topic}**

Think step-by-step:
1. **Trend Analysis**: Identify the top 3 shifts in the landscape. Are they temporary or structural?
2. **Competitive Tension**: Where are the gaps? Who is winning and why?
3. **Risk Profile**: What are the 'unknown unknowns' or potential headwinds?
4. **Strategic Levers**: What are 2-3 specific actions or 'angles' that offer the highest leverage?

Output format (strict):
## Strategic Analysis: {{topic}}

### The 'So What?': Executive Summary
[2-3 sentences of high-level strategic takeaway]

### Macro Trends & Market Shifts
1. [Trend name] — [Evidence] — [Strategic Impact]
2. ...

### Competitive Gaps & Exploitable Weaknesses
- [Specific gap] -> [Why it exists] -> [How to exploit it]

### Strategic Risks & Mitigations
- [Risk] -> [Significance] -> [Mitigation suggestion]

### Recommended Narrative Angles
- [Angle 1]: [Rationale tied to ICP needs]
{vertical_section}
""",
        expected_output="A sophisticated strategic analysis with actionable recommendations in Markdown.",
        agent=agent,
        context=[],
    )
