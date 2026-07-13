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


# ── Capability-based model registry (routed mode) ─────────────────────────────
# Routed mode picks each agent's model from its *capability* need, not a
# hardcoded per-agent slug. This makes per-role tiering work on a *single*
# provider (e.g. Groq 8B for light work, Groq 70B for reasoning) instead of
# collapsing to one model — the fix for the old design, where analyst/reviewer/
# eval were pinned to an OpenRouter model and so failed-then-fell-back on every
# call whenever only the Groq key was present. It also lets a model be added or
# repriced in one place (utils.pricing reads price straight from here).
#
#   caps          — what the model is fit to be a PRIMARY for.
#   tool_quality  — "good" models can drive the researcher's ReAct tool loop;
#                   a "poor" (non-standard tool-call format) model must never be
#                   a tool-use primary, though a provider-derived fallback leg
#                   (get_fallbacks) may still reach it as a last resort.
#   price         — (prompt_per_1k, completion_per_1k) USD; the single source of
#                   truth consumed by utils.pricing.
#   rate_limit    — informational: "token" tiers exhaust on tokens/day, "request"
#                   tiers on request count (cheap for big single-shot calls).
LIGHT, REASONING, WRITING, TOOL_USE, JUDGE = (
    "light", "reasoning", "writing", "tool_use", "judge",
)

MODEL_REGISTRY: dict[str, dict] = {
    "groq/llama-3.1-8b-instant": {
        "provider": "groq",
        "caps": {LIGHT},
        "tool_quality": "poor",
        "price": (0.00005, 0.00008),
        "rate_limit": "token",
    },
    "groq/llama-3.3-70b-versatile": {
        "provider": "groq",
        "caps": {REASONING, WRITING, TOOL_USE, JUDGE},
        "tool_quality": "good",
        "price": (0.00059, 0.00079),
        "rate_limit": "token",
    },
    "openrouter/tencent/hy3:free": {
        "provider": "openrouter",
        "caps": {REASONING, JUDGE},
        "tool_quality": "poor",
        "price": (0.0, 0.0),
        "rate_limit": "request",
    },
    # NB: Gemini is deliberately NOT a routing citizen. GEMINI_API_KEY ships set
    # for RAG embeddings (config.EMBEDDING_MODEL), and Gemini reasoning proved
    # unusable under this pipeline's burst load; since Gemini Flash would be the
    # cheapest tool-use/writing model, listing it here would let cost-first
    # silently divert the core generation path onto it. Set a *_MODEL override
    # explicitly if you ever want a Gemini reasoning model.
}

# Each agent/service's required capability. Also the valid-agent allowlist — an
# unknown name raises KeyError (as _DEFAULT_MODELS did before it).
ROLE_CAPS: dict[str, str] = {
    "strategist": LIGHT,
    "query_rewriter": LIGHT,
    "researcher": TOOL_USE,
    "lead_intel": TOOL_USE,
    "writer": WRITING,
    "editor": WRITING,
    "analyst": REASONING,
    "reviewer": JUDGE,
    "eval": JUDGE,
}


# The quality judges: the reviewer's audit and the eval-confidence judge. They
# grade the generators' output, so pinning them to the same model as the
# generators (as legacy mode otherwise does) means a model grades itself and its
# blind spots surface to the human as "AI Confidence." JUDGE_MODEL decouples them
# in every mode (see get_model — M2).
_JUDGE_AGENTS = frozenset({"reviewer", "eval"})


def _legacy_mode() -> bool:
    return settings.LLM_MODEL is not None and settings.LLM_MODEL != ""


def _generator_reference_model() -> str | None:
    """The model the generators resolve to, used to keep a judge off the same
    model it grades. A generator role is never itself a judge, so this can't
    recurse; any resolution failure just disables the decoupling preference."""
    try:
        return get_model("writer")
    except (KeyError, RuntimeError, IndexError):
        return None


def _resolve(agent_name: str) -> list[str]:
    """Routed-mode candidate models for an agent, best (primary) first.

    Filters MODEL_REGISTRY to providers whose key is present and models fit for
    the role's capability, then ranks cost-first (cheapest qualifying model wins,
    matching the free-tier-first intent). A tool-use role additionally sinks poor
    tool-callers below good ones for the *primary* slot. For a judge without
    JUDGE_MODEL, a model distinct from the generators' is preferred — generalizing
    the M2 judge/generator decoupling. get_model uses [0]; the full list is
    returned for testability.
    """
    if agent_name not in ROLE_CAPS:
        raise KeyError(f"Unknown agent name: {agent_name}")
    need = ROLE_CAPS[agent_name]

    quals = [
        slug for slug, spec in MODEL_REGISTRY.items()
        if _has_key(spec["provider"]) and need in spec["caps"]
    ]
    # Cheapest-qualifying first (cost-first policy). Python's sort is stable, so
    # the tie-break below preserves this ordering within each quality group.
    quals.sort(key=lambda s: sum(MODEL_REGISTRY[s]["price"]))

    if need == TOOL_USE:
        # A tool-use PRIMARY must drive the ReAct loop reliably; a poor
        # tool-caller drops below the good ones.
        quals.sort(key=lambda s: MODEL_REGISTRY[s]["tool_quality"] != "good")

    if need == JUDGE and not (agent_name in _JUDGE_AGENTS and settings.JUDGE_MODEL):
        gen = _generator_reference_model()
        non_gen = [s for s in quals if s != gen]
        if non_gen:  # keep the generator model only as a lower-priority option
            quals = non_gen + [s for s in quals if s == gen]

    return quals


def get_model(agent_name: str) -> str:
    """
    Resolve the model slug for an agent or service.

    Resolution order:
    1. JUDGE_MODEL — the reviewer/eval judges use it in every mode, so they never
       collapse onto the generator model they're grading (M2).
    2. Legacy LLM_MODEL — if set, every (non-judge) agent uses it.
    3. Explicit per-agent override — a set {AGENT}_MODEL env var wins over routing.
    4. Routed default — the cheapest registry model fit for the agent's capability
       (see _resolve), which works on a single provider too.
    """
    if agent_name in _JUDGE_AGENTS and settings.JUDGE_MODEL:
        return settings.JUDGE_MODEL

    if _legacy_mode():
        return settings.LLM_MODEL or ""

    override = getattr(settings, f"{agent_name.upper()}_MODEL", None)
    if override:
        return override

    candidates = _resolve(agent_name)
    if not candidates:
        raise RuntimeError(
            f"No model available for '{agent_name}' (capability "
            f"'{ROLE_CAPS[agent_name]}') — no provider key is configured for any "
            "model that can serve it."
        )
    return candidates[0]


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


def reconcile_served_model(agent_name: str, served: str | None) -> str:
    """Map a litellm-reported served model back to a *known* pricing slug for
    `agent_name`, matching it against the agent's primary + fallback candidates.
    litellm reports the bare provider model name (no ``groq/``/``openrouter/``
    prefix), so we match on that; anything unrecognized (or empty) degrades to
    the configured primary.

    Unlike resolve_actual_model this takes the served model *explicitly* (read
    off the litellm response), so it's safe for direct calls that interleave
    with other litellm traffic in the same process — e.g. the query_rewriter
    firing inside the researcher's tool loop — where the process-global
    success-hook capture would be clobbered.
    """
    primary = get_model(agent_name)
    if not served:
        return primary
    for cand in (primary, *get_fallbacks(agent_name)):
        bare = cand.split("/", 1)[1] if cand.startswith(("groq/", "openrouter/")) else cand
        if served in (cand, bare) or bare.endswith(served) or served.endswith(bare):
            return cand
    return primary


def resolve_actual_model(agent_name: str) -> str:
    """The model that actually served this agent's crew-node kickoff, as a known
    pricing slug (the configured primary, or a fallback slug if litellm spilled).

    Relies on crew nodes running one at a time (Celery --concurrency=1, linear
    graph), so the last globally-captured served model belongs to this node's
    kickoff. Direct (non-crew) callers should use reconcile_served_model with the
    served model off their own response instead of this global.
    """
    return reconcile_served_model(agent_name, _actual_model_used["model"])
