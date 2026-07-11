"""
USD pricing per model slug, used to turn the token counts already tracked in
`token_usages` into an actual dollar figure (§4.1 — `_log_token_usages` used to
hardcode `total_cost=0.0` for every call, so `RunCost.total_cost` and the
`/analytics/costs` endpoint always reported $0.00 regardless of real spend).

Keyed by the exact model slug `services.llm_router.get_model` resolves — the
same defaults declared in `llm_router._DEFAULT_MODELS`, plus common paid
overrides someone might set via the per-agent `*_MODEL` env vars. Prices are
USD per 1,000 tokens, split prompt/completion, taken from each provider's
public pricing page at time of writing — expect drift over time, not a
live-updated feed.
"""
from logger import logger

# (prompt_price_per_1k_usd, completion_price_per_1k_usd)
_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    # Defaults in llm_router._DEFAULT_MODELS
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "groq/llama-3.1-8b-instant": (0.00005, 0.00008),
    "groq/llama-3.3-70b-versatile": (0.00059, 0.00079),
    # Common paid overrides via *_MODEL env vars / LLM_MODEL legacy mode
    "openrouter/openai/gpt-4o": (0.0025, 0.01),
    "openrouter/openai/gpt-4o-mini": (0.00015, 0.0006),
    "openrouter/anthropic/claude-3.5-sonnet": (0.003, 0.015),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gemini/gemini-1.5-flash": (0.000075, 0.0003),
    "gemini/gemini-1.5-pro": (0.00125, 0.005),
    "gemini/gemini-2.0-flash": (0.0001, 0.0004),
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
