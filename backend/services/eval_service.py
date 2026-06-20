import json
from litellm import acompletion
from config import settings


async def evaluate_output(content: str, research: str, topic: str) -> dict:
    """
    Score output on 4 dimensions (0-100 each).
    Returns: { accuracy, relevance, completeness, writing_quality, overall, issues }
    """
    prompt = f"""You are a quality evaluator. Score this content on 4 dimensions (0-100):
1. Accuracy: Are all claims supported by the research?
2. Relevance: Does it address the topic directly?
3. Completeness: Are all required sections present and substantive?
4. Writing Quality: Is it clear, engaging, and professional?

Topic: {topic}

Research Summary:
{research[:2000]}

Content to Evaluate:
{content[:3000]}

Respond ONLY with valid JSON:
{{"accuracy": 85, "relevance": 90, "completeness": 78, "writing_quality": 88, "overall": 85, "issues": ["list any critical issues"]}}"""

    response = await acompletion(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL or None,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
