from crewai import Agent, Task
from tools.search import tavily_search_tool
from tools.scraper import firecrawl_tool
from config import settings


def lead_intel_agent() -> Agent:
    return Agent(
        role="Lead Intelligence Analyst",
        goal="Build a comprehensive prospect dossier for a given company URL.",
        backstory=(
            "You are a B2B sales intelligence specialist. You scrape company websites, "
            "search for funding news, identify decision makers, and score fit. "
            "You are precise, cite every source, and never fabricate names or titles."
        ),
        tools=[tavily_search_tool, firecrawl_tool],
        llm=settings.LLM_MODEL,
        verbose=True,
        max_iter=10,
    )


def lead_intel_task(agent: Agent, company_url: str) -> Task:
    # Extract vertical playbook from topic if present
    vertical_section = ""
    if "**Vertical Playbook**:" in company_url:
        vertical_section = (
            "\n\n**IMPORTANT — Vertical Playbook Active**\n"
            "Follow the research focus and required output sections from the playbook. "
            "If a target buyer role or product value prop is specified, tailor the "
            "Fit Score reasoning and Recommended Outreach Angle to those specifics."
        )

    return Task(
        description=f"""
Build a prospect dossier for: **{company_url}**

Steps:
1. Use Firecrawl to scrape the company homepage and /about page.
2. Use Tavily to search: "{{company_url}} funding news 2024 2025"
3. Use Tavily to search: "{{company_url}} leadership team CEO CTO"
4. Use Firecrawl to scrape the company LinkedIn page if available.
5. Use Tavily to search: "{{company_url}} tech stack jobs engineering"

Output format (strict):
## Company Dossier: {{company_name}}

### Company Overview
- **Size**: [headcount estimate]
- **Founded**: [year]
- **HQ**: [city, country]
- **Funding**: [total raised, last round, investors]
- **Website**: {{company_url}}

### Key Decision Makers
| Name | Title | LinkedIn |
|------|-------|---------|
| [name] | [title] | [url or N/A] |

### Recent News (last 3 months)
- [headline — source — date]

### Technology Stack
- [tech 1 — source]
- [tech 2 — source]

### Fit Score
**Score: X/10**
**Reasoning**: [2–3 sentences explaining the score]
{vertical_section}
""",
        expected_output="A structured company dossier in Markdown with all sections populated.",
        agent=agent,
    )
