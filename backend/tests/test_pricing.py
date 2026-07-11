"""
Regression tests for §4.1: `_log_token_usages` used to hardcode
`total_cost=0.0` for every call, so `RunCost.total_cost` (and the
`/analytics/costs` endpoint's `total_cost_usd`) always reported $0.00
regardless of real spend.
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


def test_calculate_cost_unknown_model_falls_back_to_zero():
    assert calculate_cost("some/unpriced-model", 1000, 1000) == 0.0


def test_calculate_cost_scales_with_tokens():
    cost_small = calculate_cost("gpt-4o-mini", 100, 100)
    cost_large = calculate_cost("gpt-4o-mini", 1000, 1000)
    assert cost_large == cost_small * 10
