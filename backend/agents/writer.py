from crewai import Agent, Task
from services.llm_router import get_model

FORMAT_INSTRUCTIONS = {
    "report": """
Write a full research report (1,500–2,500 words) with these sections:
- Executive Summary (150 words)
- Introduction & Context
- Key Findings (with sub-sections per theme)
- Data & Statistics (use a markdown table)
- Strategic Implications
- Recommendations
- Conclusion
- References (cite all sources from research)
""",
    "linkedin": """
Write a LinkedIn article (1,200–1,500 words) with:
- A strong hook opening (2–3 sentences, bold claim or surprising stat)
- 4–5 insight sections with short headers
- Concrete examples and data points
- A closing call-to-action paragraph
- Professional but conversational tone
- NO hashtags in the body (add 3–5 at the very end)
""",
    "summary": """
Write a one-page executive summary (400–600 words) with:
- Title
- Situation (2–3 sentences of context)
- Key Findings (5 bullet points max)
- Strategic Implications (3 bullet points)
- Recommended Next Steps (3 action items)
Use concise, business-appropriate language.
""",
}

def writer_agent() -> Agent:
    return Agent(
        role="Senior Content Strategist",
        goal="Transform complex strategic insights into compelling, publication-ready narratives that drive reader engagement.",
        backstory=(
            "You are a master storyteller with a background in premium business journalism (FT, WSJ). "
            "You know how to hook a busy executive in the first sentence. "
            "You write with clarity, authority, and rhythm. You avoid corporate jargon and filler. "
            "You are expert at organizing information into a hierarchy that makes it easy to scan "
            "while retaining depth. You treat every citation as a badge of authority."
        ),
        tools=[],
        llm=get_model("writer"),
        verbose=True,
        max_iter=3,
    )

def write_task(agent: Agent, topic: str, output_format: str) -> Task:
    instructions = FORMAT_INSTRUCTIONS.get(output_format, FORMAT_INSTRUCTIONS["report"])

    # Extract vertical-specific output sections if present
    vertical_section = ""
    if "**Required Output Sections**:" in topic:
        vertical_section = (
            "\n\n**VERTICAL MANDATE**\n"
            "You MUST use the Required Output Sections from the topic brief as your primary headings (H2/H3). "
            "Do not skip any section. Ensure the flow between these sections is logical and professional."
        )

    return Task(
        description=f"""
Using the research and strategic analysis, write the final content for: **{topic}**

Think step-by-step:
1. **The Hook**: Craft an opening that highlights the most surprising or significant finding.
2. **Structure**: Map the insights to the requested {output_format} format.
3. **Evidence Integration**: Weave statistics and citations naturally into the prose.
4. **Tone Check**: Ensure the voice matches the target audience (e.g. Founder, Sales Leader).

Format instructions:
{instructions}

Rules:
- NO boilerplate openings like "In today's fast-paced world...".
- Use Markdown for structure (H1, H2, tables, bolding).
- Ensure all sources from the research are cited using Markdown links.
{vertical_section}
""",
        expected_output=f"A polished, high-impact {output_format} in Markdown format.",
        agent=agent,
    )
