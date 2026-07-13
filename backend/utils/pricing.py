"""
USD pricing per model slug, used to turn the token counts already tracked in
`token_usages` into an actual dollar figure (§4.1 — `_log_token_usages` used to
hardcode `total_cost=0.0` for every call, so `RunCost.total_cost` and the
`/analytics/costs` endpoint always reported $0.00 regardless of real spend).

Prices for the routed models come straight from
`services.llm_router.MODEL_REGISTRY` (its single source of truth), extended here
with common paid slugs someone might set via the per-agent `*_MODEL` env vars or
`LLM_MODEL` legacy mode. Prices are USD per 1,000 tokens, split prompt/completion,
taken from each provider's public pricing page at time of writing — expect drift
over time, not a live-updated feed.
"""
from logger import logger

from services.llm_router import MODEL_REGISTRY

# (prompt_price_per_1k_usd, completion_price_per_1k_usd). Paid/legacy slugs the
# registry doesn't route to but an operator might pin via *_MODEL / LLM_MODEL.
_PAID_OVERRIDES: dict[str, tuple[float, float]] = {
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "openrouter/openai/gpt-4o": (0.0025, 0.01),
    "openrouter/openai/gpt-4o-mini": (0.00015, 0.0006),
    "openrouter/anthropic/claude-3.5-sonnet": (0.003, 0.015),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gemini/gemini-1.5-flash": (0.000075, 0.0003),
    "gemini/gemini-1.5-pro": (0.00125, 0.005),
    # Gemini isn't a routing citizen (see llm_router.MODEL_REGISTRY), but keep it
    # priced for anyone who pins it via a *_MODEL / LLM_MODEL override.
    "gemini/gemini-2.0-flash": (0.0001, 0.0004),
}

# Registry prices are authoritative for routed models (e.g. this is what adds
# openrouter/tencent/hy3:free, which used to log unknown_model_pricing on every
# analyst/judge call); paid overrides fill in the rest.
_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    **{slug: spec["price"] for slug, spec in MODEL_REGISTRY.items()},
    **_PAID_OVERRIDES,
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return USD cost for a call, or 0.0 (with a logged warning) for a model
    not in the table — an unpriced override should degrade to "cost unknown"
    rather than crash the run."""
    pricing = _PRICING_PER_1K.get(model)
    if pricing is None:
        logger.warning("unknown_model_pricing", model=model)
        return 0.0
    prompt_price, completion_price = pricing
    return (prompt_tokens / 1000) * prompt_price + (completion_tokens / 1000) * completion_price
