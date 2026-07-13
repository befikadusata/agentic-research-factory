from dataclasses import dataclass

import litellm

from config import settings


@dataclass(frozen=True)
class LLMSelection:
    model: str
    api_key: str | None = None
    base_url: str | None = None
    # Cross-provider fallbacks tried by litellm (in order) when the primary call
    # errors — e.g. a free-tier 429. Derived from the primary's provider and
    # gated on the peer provider's key being present (see get_fallbacks).
    fallbacks: tuple[str, ...] = ()


# Cross-provider fallback targets. The whole point of spreading agents across two
# free tiers is that when one is exhausted/rate-limited, the other absorbs the
# call instead of failing the run. So a Groq-primary agent spills to OpenRouter
# free, and an OpenRouter-primary agent spills to Groq. litellm reads each
# provider's key from the env vars config.py already exports, so no per-call key
# wiring is needed for the fallback leg.
_GROQ_FALLBACK = "groq/llama-3.3-70b-versatile"
# Tencent Hunyuan hy3 (free): currently the reliably-available OpenRouter free
# model — the meta-llama :free slug is frequently 429 "rate-limited upstream".
_OPENROUTER_FALLBACK = "openrouter/tencent/hy3:free"


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


# The quality judges: the reviewer's audit and the eval-confidence judge. They
# grade the generators' output, so pinning them to the same model as the
# generators (as legacy mode otherwise does) means a model grades itself and its
# blind spots surface to the human as "AI Confidence." JUDGE_MODEL decouples them
# in every mode (see get_model — M2).
_JUDGE_AGENTS = frozenset({"reviewer", "eval"})


def _legacy_mode() -> bool:
    return settings.LLM_MODEL is not None and settings.LLM_MODEL != ""


def get_model(agent_name: str) -> str:
    """
    Resolve the model slug for an agent or service.

    Judge override:
    - If JUDGE_MODEL is set, the reviewer and eval judge use it regardless of
      mode, so they never collapse onto the generator model they're grading (M2).

    Legacy behavior:
    - If LLM_MODEL is set, every (non-judge) agent uses it.

    Routed behavior:
    - Otherwise, the per-agent defaults above are used and can be overridden in .env.
    - Raw OpenRouter slugs like meta-llama/...:free are routed through OpenRouter.
    """
    if agent_name in _JUDGE_AGENTS and settings.JUDGE_MODEL:
        return settings.JUDGE_MODEL

    if _legacy_mode():
        return settings.LLM_MODEL or ""

    if agent_name not in _DEFAULT_MODELS:
        raise KeyError(f"Unknown agent name: {agent_name}")

    override = getattr(settings, f"{agent_name.upper()}_MODEL", None)
    return override or _DEFAULT_MODELS[agent_name]


def _has_key(provider: str | None) -> bool:
    """Whether the credentials for a provider's fallback leg are actually set.

    A fallback we can't authenticate is worse than none — it just adds a failing
    round-trip on every error — so a cross-provider fallback is only offered when
    that provider's key is configured.
    """
    if provider == "groq":
        return bool(settings.GROQ_API_KEY)
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    if provider in {"gemini", "google"}:
        return bool(settings.GEMINI_API_KEY)
    return False


def get_fallbacks(agent_name: str) -> list[str]:
    """Cross-provider fallback model(s) for an agent, derived from its primary.

    A Groq-primary agent falls back to OpenRouter free and vice versa, so a
    free-tier 429 on one provider is absorbed by the other instead of failing the
    whole run. This holds in *both* legacy (single pinned LLM_MODEL) and routed
    mode — keyed off the primary's provider and gated on the peer provider having
    a key. (Previously legacy mode hard-returned [], which disabled the entire
    fallback layer in the one mode that actually ships — H1.)

    A custom LLM_BASE_URL (a legacy openai-compatible endpoint) can't be sanely
    spilled to a different provider, so no cross-provider fallback there.
    """
    if _legacy_mode() and settings.LLM_BASE_URL:
        return []
    provider = _provider_from_model(get_model(agent_name))
    if provider == "groq" and _has_key("openrouter"):
        return [_OPENROUTER_FALLBACK]
    if provider == "openrouter" and _has_key("groq"):
        return [_GROQ_FALLBACK]
    return []  # gemini/unknown, or the peer key is absent: no usable fallback


def get_llm(agent_name: str, max_tokens: int | None = None):
    """Build a CrewAI LLM for an agent, wired with its cross-provider fallback.

    Agents pass this to `Agent(llm=...)`. Keys are read from the environment
    (config.py exports GROQ/OPENROUTER keys), so both the primary and the
    fallback leg authenticate without any per-call key wiring here.

    max_tokens caps the completion length. It's used to keep token-heavy agents
    (the researcher) under Groq's free 12K tokens/min ceiling: a smaller
    completion reservation means each call requests fewer tokens, so a full pass
    fits inside one rate-limit window instead of 429-ing mid-run.
    """
    from crewai import LLM

    kwargs = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return LLM(model=get_model(agent_name), fallbacks=get_fallbacks(agent_name), **kwargs)


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
            fallbacks=tuple(get_fallbacks(agent_name)),
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


# ── H4: attribute cost to the model that actually served the call ─────────────
# On a fallback leg the served model differs from the configured primary, so
# pricing the call against the primary is wrong exactly during a provider
# outage. litellm reports the served model on every successful completion; we
# capture it via a global success hook (a plain function, so CrewAI's own
# callback wiring — which only de-dupes litellm callbacks by *type* — leaves it
# in place) and reconcile it back to a known pricing slug.
_actual_model_used: dict[str, str | None] = {"model": None}


def _capture_actual_model(kwargs, response_obj, start_time, end_time) -> None:
    model = getattr(response_obj, "model", None) or (kwargs or {}).get("model")
    if model:
        _actual_model_used["model"] = model


if _capture_actual_model not in litellm.success_callback:
    litellm.success_callback.append(_capture_actual_model)


def reset_actual_model() -> None:
    """Clear the captured served-model before a crew node runs, so a stale value
    from a previous node can't leak into this one's cost attribution."""
    _actual_model_used["model"] = None


def resolve_actual_model(agent_name: str) -> str:
    """The model that actually served this agent's call, as a *known* pricing
    slug. Returns the configured primary unless litellm reported a different
    served model (a fallback fired) that matches one of the agent's declared
    fallback candidates. litellm reports the bare provider model name (no
    ``groq/``/``openrouter/`` prefix), so we match on that. Anything
    unrecognized degrades to the primary.

    Relies on crew nodes running one at a time (Celery --concurrency=1, linear
    graph), so the last captured model belongs to this node's kickoff.
    """
    primary = get_model(agent_name)
    served = _actual_model_used["model"]
    if not served:
        return primary
    for cand in (primary, *get_fallbacks(agent_name)):
        bare = cand.split("/", 1)[1] if cand.startswith(("groq/", "openrouter/")) else cand
        if served in (cand, bare) or bare.endswith(served) or served.endswith(bare):
            return cand
    return primary
