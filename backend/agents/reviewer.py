from crewai import Agent, Task
from services.llm_router import get_model

def reviewer_agent() -> Agent:
    return Agent(
        role="Quality Assurance Auditor",
        goal="Provide a rigorous, fact-based audit of research and analysis to ensure it meets institutional-grade standards.",
        backstory=(
            "You are a meticulous auditor with a background in fact-checking for major financial news outlets. "
            "You have a 'trust but verify' mindset. You look for logical fallacies, unsupported claims, "
            "and generic AI 'filler'. You ensure that every metric is cited and every strategic claim "
            "is grounded in the provided research summary. You are the final gatekeeper of quality."
        ),
        tools=[],
        llm=get_model("reviewer"),
        verbose=True,
    )

def review_task(agent: Agent, topic: str, current_output: str, rubric: str) -> Task:
    return Task(
        description=f"""
Audit the following work for the topic: **{topic}**

**Quality Rubric**:
{rubric}

**Work Under Review**:
{current_output}

Think step-by-step:
1. **Fact Check**: Cross-reference at least 3 key claims in the Analysis with the Research Summary. Are they supported?
2. **Citation Integrity**: Are all URLs valid? Are they used appropriately?
3. **Logic Check**: Does the 'So What?' actually follow from the data?
4. **Vertical Compliance**: Are the specific requirements of the playbook addressed?

Output format:
### Quality Audit: [PASS] or [FAIL]

#### Critical Findings:
- [Finding 1: e.g. 'Uncited TAM figure']
- [Finding 2: e.g. 'Missing competitive gap section']

#### Actionable Feedback for Improvement:
[If FAIL, provide 2-3 specific steps to fix. If PASS, provide 1-2 ways to make it even stronger.]
""",
        expected_output="A rigorous quality audit report with a binary PASS/FAIL decision and detailed findings.",
        agent=agent,
    )
