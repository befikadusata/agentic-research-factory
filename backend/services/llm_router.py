from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class LLMSelection:
    model: str
    api_key: str | None = None
    base_url: str | None = None


_DEFAULT_MODELS: dict[str, str] = {
    "strategist": "groq/llama-3.1-8b-instant",
    "researcher": "meta-llama/llama-3.3-70b-instruct:free",
    "lead_intel": "meta-llama/llama-3.3-70b-instruct:free",
    "query_rewriter": "groq/llama-3.1-8b-instant",
    "analyst": "openrouter/free",
    "writer": "openrouter/free",
    "editor": "openrouter/free",
    "reviewer": "openrouter/free",
    "eval": "openrouter/free",
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

    provider = _provider_from_model(model)
    if provider == "groq":
        return LLMSelection(model=model, api_key=settings.GROQ_API_KEY)
    if provider == "openrouter":
        return LLMSelection(model=model, api_key=settings.OPENROUTER_API_KEY)
    if provider in {"gemini", "google"}:
        return LLMSelection(model=model, api_key=settings.GEMINI_API_KEY)

    return LLMSelection(model=model)
