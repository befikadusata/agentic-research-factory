from crewai import Agent, Task
from config import settings

def strategist_agent() -> Agent:
    return Agent(
        role="Lead Research Strategist",
        goal="Develop a high-precision execution roadmap that aligns research efforts with specific vertical requirements and strategic objectives.",
        backstory=(
            "You are a premier information architect and former Director of Strategy at a top-tier consultancy. "
            "You specialize in decomposing complex, ambiguous requests into surgical research plans. "
            "Your strength lies in identifying exactly what data points will move the needle for a decision-maker. "
            "You think three steps ahead, anticipating the analysis and writing needs from the very start."
        ),
        tools=[],
        llm=settings.LLM_MODEL,
        verbose=True,
    )

def planning_task(agent: Agent, topic: str) -> Task:
    return Task(
        description=f"""
Analyze the research request and vertical playbook: **{topic}**

Your mission is to create a 'Mission Command' Research & Analysis Plan. 
Think step-by-step:
1. **Critical Hypotheses**: What are we trying to prove or disprove?
2. **Data Requirements**: What specific metrics, news signals, or competitive details are non-negotiable?
3. **Search Strategy**: Map out the primary keywords and specify if 'deep' (Firecrawl) or 'wide' (Tavily snippets) search is needed for each angle.
4. **Analytical Lens**: Which frameworks (SWOT, Porter's, Value Chain) will best serve the final format?
5. **Quality Benchmarks**: Define what 'excellent' looks like for this specific output.

Keep the plan laser-focused and actionable. Avoid fluff.
""",
        expected_output="A structured Research & Analysis Plan in Markdown format.",
        agent=agent,
    )
