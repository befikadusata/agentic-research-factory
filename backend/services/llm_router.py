from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class LLMSelection:
    model: str
    api_key: str | None = None
    base_url: str | None = None
    # Cross-provider fallbacks tried by litellm (in order) when the primary call
    # errors — e.g. a free-tier 429. Empty in legacy mode (single pinned model).
    fallbacks: tuple[str, ...] = ()


# Cross-provider fallback targets. The whole point of spreading agents across two
# free tiers is that when one is exhausted/rate-limited, the other absorbs the
# call instead of failing the run. So a Groq-primary agent spills to OpenRouter
# free, and an OpenRouter-primary agent spills to Groq. litellm reads each
# provider's key from the env vars config.py already exports, so no per-call key
# wiring is needed for the fallback leg.
_GROQ_FALLBACK = "groq/llama-3.3-70b-versatile"
_OPENROUTER_FALLBACK = "openrouter/meta-llama/llama-3.3-70b-instruct:free"


_DEFAULT_MODELS: dict[str, str] = {
    "strategist": "groq/llama-3.1-8b-instant",
    "researcher": "meta-llama/llama-3.3-70b-instruct:free",
    "lead_intel": "meta-llama/llama-3.3-70b-instruct:free",
    "query_rewriter": "groq/llama-3.1-8b-instant",
    "analyst":  "meta-llama/llama-3.3-70b-instruct:free",
    "writer":   "meta-llama/llama-3.3-70b-instruct:free",
    "editor":   "meta-llama/llama-3.3-70b-instruct:free",
    "reviewer": "meta-llama/llama-3.3-70b-instruct:free",
    "eval":     "meta-llama/llama-3.3-70b-instruct:free",
}


def _legacy_mode() -> bool:
    return settings.LLM_MODEL is not None and settings.LLM_MODEL != ""


def get_model(agent_name: str) -> str:
    """
    Resolve the model slug for an agent or service.

    Legacy behavior:
    - If LLM_MODEL is set, every agent uses it.

    Routed behavior:
    - Otherwise, the per-agent defaults above are used and can be overridden in .env.
    - Raw OpenRouter slugs like meta-llama/...:free are routed through OpenRouter.
    """
    if _legacy_mode():
        return settings.LLM_MODEL or ""

    if agent_name not in _DEFAULT_MODELS:
        raise KeyError(f"Unknown agent name: {agent_name}")

    override = getattr(settings, f"{agent_name.upper()}_MODEL", None)
    return override or _DEFAULT_MODELS[agent_name]


def get_fallbacks(agent_name: str) -> list[str]:
    """Cross-provider fallback model(s) for an agent, derived from its primary.

    In legacy mode every agent is pinned to the one LLM_MODEL, so there is no
    fallback (returning [] keeps that behavior a hard single-model choice). In
    routed mode a Groq-primary agent falls back to OpenRouter free and vice
    versa, so a free-tier 429 on one provider is absorbed by the other rather
    than failing the whole run.
    """
    if _legacy_mode():
        return []
    provider = _provider_from_model(get_model(agent_name))
    if provider == "groq":
        return [_OPENROUTER_FALLBACK]
    if provider == "openrouter":
        return [_GROQ_FALLBACK]
    return []  # gemini/unknown: no cross-provider peer to fall back to


def get_llm(agent_name: str):
    """Build a CrewAI LLM for an agent, wired with its cross-provider fallback.

    Agents pass this to `Agent(llm=...)`. Keys are read from the environment
    (config.py exports GROQ/OPENROUTER keys), so both the primary and the
    fallback leg authenticate without any per-call key wiring here.
    """
    from crewai import LLM

    return LLM(model=get_model(agent_name), fallbacks=get_fallbacks(agent_name))


def _provider_from_model(model: str) -> str | None:
    if model.startswith("gemini") or model.startswith("google/"):
        return "gemini"
    if "/" not in model:
        return None
    prefix = model.split("/", 1)[0]
    if prefix == "groq":
        return "groq"
    if prefix == "openrouter":
        return "openrouter"
    # Raw OpenRouter slugs such as meta-llama/...:free and qwen/... are routed
    # through OpenRouter.
    return "openrouter"


def get_completion_settings(agent_name: str) -> LLMSelection:
    """
    Resolve model + credentials for direct LiteLLM calls.
    """
    model = get_model(agent_name)

    if _legacy_mode():
        return LLMSelection(
            model=model,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL or None,
        )

    fallbacks = tuple(get_fallbacks(agent_name))
    provider = _provider_from_model(model)
    if provider == "groq":
        return LLMSelection(model=model, api_key=settings.GROQ_API_KEY, fallbacks=fallbacks)
    if provider == "openrouter":
        return LLMSelection(model=model, api_key=settings.OPENROUTER_API_KEY, fallbacks=fallbacks)
    if provider in {"gemini", "google"}:
        return LLMSelection(model=model, api_key=settings.GEMINI_API_KEY, fallbacks=fallbacks)

    return LLMSelection(model=model, fallbacks=fallbacks)
