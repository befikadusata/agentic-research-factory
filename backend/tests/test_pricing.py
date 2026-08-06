"""
`calculate_cost` is what turns tracked token counts into the dollar figure
`RunCost.total_cost` and `/analytics/costs` report, so every slug the pipeline
can actually route to must be priced here.
"""
from utils.pricing import calculate_cost


def test_calculate_cost_known_model():
    cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=1000)
    assert cost == (0.0025 * 1) + (0.01 * 1)


def test_calculate_cost_groq_70b_default_is_priced():
    # The pipeline's default LLM_MODEL (groq/llama-3.3-70b-versatile) must be
    # priced, or /analytics/costs reports $0 for every real run.
    cost = calculate_cost("groq/llama-3.3-70b-versatile", 1000, 1000)
    assert cost == (0.00059 * 1) + (0.00079 * 1)
    assert cost > 0


def test_calculate_cost_free_model_is_zero():
    assert calculate_cost("meta-llama/llama-3.3-70b-instruct:free", 5000, 5000) == 0.0


def test_calculate_cost_routed_free_openrouter_model_is_priced():
    # The cross-provider fallback slug must be present in the pricing table, or
    # every fallback leg logs unknown_model_pricing. It happens to price to $0,
    # which the assertion alone can't tell apart from the unknown-model default.
    assert calculate_cost("openrouter/tencent/hy3:free", 5000, 5000) == 0.0


def test_calculate_cost_matches_registry_price():
    # Registry is the single source of truth for routed-model pricing.
    from services.llm_router import MODEL_REGISTRY

    prompt_price, completion_price = MODEL_REGISTRY["groq/llama-3.1-8b-instant"]["price"]
    cost = calculate_cost("groq/llama-3.1-8b-instant", 1000, 1000)
    assert cost == prompt_price + completion_price


def test_calculate_cost_unknown_model_falls_back_to_zero():
    assert calculate_cost("some/unpriced-model", 1000, 1000) == 0.0


def test_calculate_cost_scales_with_tokens():
    cost_small = calculate_cost("gpt-4o-mini", 100, 100)
    cost_large = calculate_cost("gpt-4o-mini", 1000, 1000)
    assert cost_large == cost_small * 10
