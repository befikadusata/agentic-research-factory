from litellm import acompletion
from services.llm_router import get_completion_settings
from utils.context import compact_text
from utils.cost_tracker import log_direct_call
from utils.json_parse import parse_json


async def evaluate_output(
    content: str,
    research: str,
    topic: str,
    run_id=None,
    agent_name: str = "eval",
    evaluation_requirements: str | None = None,
) -> dict:
    """
    Score output on 4 dimensions (0-100 each).
    Returns: { accuracy, relevance, completeness, writing_quality, overall, issues }

    This judge is a direct litellm call (not a crew node), so it runs at every
    approval gate without being counted anywhere. When `run_id` is given its
    cost is persisted to run_costs under `agent_name`, so /analytics/costs stops
    under-reporting the judge traffic.
    """
    specialized = ""
    score_shape = ""
    if evaluation_requirements:
        specialized = f"""
Additional required dimensions (score each 0-100):
{evaluation_requirements}
Critical failure in any additional dimension must be listed in issues and must materially lower overall.
"""
        score_shape = ', "buyer_role_coverage": 90, "title_freshness": 85, "purchase_readiness": 80'

    prompt = f"""You are a quality evaluator. Score this content on 4 dimensions (0-100):
1. Accuracy: Are all claims supported by the research?
2. Relevance: Does it address the topic directly?
3. Completeness: Are all required sections present and substantive?
4. Writing Quality: Is it clear, engaging, and professional?
{specialized}

Topic: {topic}

Research Summary:
{compact_text(research, 2000)}

Content to Evaluate:
{compact_text(content, 3000)}

Respond ONLY with valid JSON:
{{"accuracy": 85, "relevance": 90, "completeness": 78, "writing_quality": 88{score_shape}, "overall": 85, "issues": ["list any critical issues"]}}"""

    llm = get_completion_settings("eval")
    response = await acompletion(
        model=llm.model,
        api_key=llm.api_key,
        base_url=llm.base_url,
        fallbacks=list(llm.fallbacks),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        timeout=60,
    )
    if run_id is not None:
        await log_direct_call(run_id, agent_name, response, routing_agent="eval")
    return parse_json(response.choices[0].message.content)
