import pytest

import services.llm_router as lr
from config import settings
from services.llm_router import get_completion_settings, get_fallbacks, get_model


def _routed(monkeypatch, groq=True, openrouter=True, gemini=False):
    """Put the router in routed mode with an explicit set of available provider
    keys and no per-agent overrides, so capability resolution is deterministic
    regardless of what the ambient .env sets."""
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "JUDGE_MODEL", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "groq-key" if groq else "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-key" if openrouter else "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gem-key" if gemini else "")
    for name in ("STRATEGIST", "QUERY_REWRITER", "RESEARCHER", "WRITER", "EDITOR",
                 "LEAD_INTEL", "ANALYST", "REVIEWER", "EVAL"):
        monkeypatch.setattr(settings, f"{name}_MODEL", None)


def test_get_model_uses_legacy_override(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "legacy/model")
    monkeypatch.setattr(settings, "JUDGE_MODEL", None)

    assert get_model("researcher") == "legacy/model"


# The judges (reviewer + eval) must be able to differ from the generators they
# grade. Otherwise, in legacy mode every agent collapses onto LLM_MODEL and a
# model grades its own output, surfaced to the human as "AI Confidence."

def test_judge_model_overrides_generators_in_legacy_mode(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "JUDGE_MODEL", "groq/llama-3.1-8b-instant")

    assert get_model("researcher") == "groq/llama-3.3-70b-versatile"
    assert get_model("reviewer") == "groq/llama-3.1-8b-instant"
    assert get_model("eval") == "groq/llama-3.1-8b-instant"


def test_judge_model_overrides_in_routed_mode(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "JUDGE_MODEL", "groq/llama-3.1-8b-instant")
    monkeypatch.setattr(settings, "REVIEWER_MODEL", "openrouter/tencent/hy3:free")

    assert get_model("reviewer") == "groq/llama-3.1-8b-instant"


def test_judges_follow_normal_resolution_when_judge_model_unset(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "legacy/model")
    monkeypatch.setattr(settings, "JUDGE_MODEL", None)

    assert get_model("reviewer") == "legacy/model"
    assert get_model("eval") == "legacy/model"


# The cross-provider fallback layer must stay live in legacy mode. Legacy
# (LLM_MODEL set) is the mode that actually ships, so returning no fallbacks
# there makes the whole resilience layer dead code in production.

def test_legacy_mode_derives_fallback_when_peer_key_present(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-key")

    # A Groq-pinned legacy model spills to OpenRouter free on a 429.
    assert get_fallbacks("researcher") == ["openrouter/tencent/hy3:free"]


def test_legacy_mode_no_fallback_without_peer_key(monkeypatch):
    # A fallback we can't authenticate is worse than none, so absent the peer
    # provider's key the pinned model stays a hard single-model choice.
    monkeypatch.setattr(settings, "LLM_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    assert get_fallbacks("researcher") == []


def test_legacy_custom_base_url_stays_single_model(monkeypatch):
    # A custom openai-compatible endpoint can't be sanely spilled to a different
    # provider — no cross-provider fallback there regardless of keys.
    monkeypatch.setattr(settings, "LLM_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://my-endpoint.example")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-key")

    assert get_fallbacks("researcher") == []


def test_groq_primary_falls_back_to_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-key")

    fallbacks = get_fallbacks("researcher")

    assert fallbacks == ["openrouter/tencent/hy3:free"]


def test_openrouter_primary_falls_back_to_groq(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "ANALYST_MODEL", "openrouter/meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "groq-key")

    fallbacks = get_fallbacks("analyst")

    assert fallbacks == ["groq/llama-3.3-70b-versatile"]


def test_fallback_suppressed_when_peer_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    assert get_fallbacks("researcher") == []


def test_completion_settings_carries_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "EVAL_MODEL", "openrouter/meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "groq-key")

    llm = get_completion_settings("eval")

    assert llm.fallbacks == ("groq/llama-3.3-70b-versatile",)


def test_get_completion_settings_uses_provider_key(monkeypatch):
    _routed(monkeypatch, groq=False, openrouter=True, gemini=False)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")
    # hy3 is no longer a routed primary (see MODEL_REGISTRY), so pin an OpenRouter
    # slug explicitly to exercise the openrouter key-wiring path.
    monkeypatch.setattr(settings, "ANALYST_MODEL", "openrouter/tencent/hy3:free")

    llm = get_completion_settings("analyst")

    assert llm.model == "openrouter/tencent/hy3:free"
    assert llm.api_key == "openrouter-test-key"


def test_get_completion_settings_treats_raw_openrouter_slugs_as_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")

    llm = get_completion_settings("researcher")

    assert llm.model == "meta-llama/llama-3.3-70b-instruct:free"
    assert llm.api_key == "openrouter-test-key"


# Cost must be attributed to the model that actually served the call. litellm
# reports the served model on each success (the bare provider name, no litellm
# prefix); resolve_actual_model reconciles it back to a known pricing slug — the
# primary normally, the fallback slug when a fallback leg ran.

class _Resp:
    def __init__(self, model):
        self.model = model


def test_resolve_actual_model_defaults_to_primary_without_capture(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "ANALYST_MODEL", "openrouter/tencent/hy3:free")
    lr.reset_actual_model()

    assert lr.resolve_actual_model("analyst") == "openrouter/tencent/hy3:free"


def test_resolve_actual_model_matches_primary_served(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "groq/llama-3.3-70b-versatile")
    lr.reset_actual_model()
    lr._capture_actual_model({}, _Resp("llama-3.3-70b-versatile"), 0, 0)

    assert lr.resolve_actual_model("researcher") == "groq/llama-3.3-70b-versatile"


def test_resolve_actual_model_maps_served_fallback_to_known_slug(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-key")
    lr.reset_actual_model()
    # The OpenRouter fallback fired; litellm reports the bare served model.
    lr._capture_actual_model({}, _Resp("tencent/hy3:free"), 0, 0)

    assert lr.resolve_actual_model("researcher") == "openrouter/tencent/hy3:free"


def test_resolve_actual_model_unknown_served_degrades_to_primary(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "groq/llama-3.3-70b-versatile")
    lr.reset_actual_model()
    lr._capture_actual_model({}, _Resp("some-unrelated-model"), 0, 0)

    assert lr.resolve_actual_model("researcher") == "groq/llama-3.3-70b-versatile"


# Capability-based routing: per-role tiering that stays correct on a single
# provider. Routing is keyed by each role's capability (llm_router.ROLE_CAPS)
# against a model registry, ranked cost-first, so a role never pins a model
# whose provider key is absent and eats a failing fallback round-trip.

def test_routed_groq_and_openrouter_reproduces_current_mapping(monkeypatch):
    # With both keys (the shipped setup) every role resolves to a Groq model:
    # 8B for light work, 70B for the reasoning/writing/tool-use/judge path. The
    # only OpenRouter free model (hy3) is not a routed primary — it returns empty
    # content under crewai — so it never wins a role here.
    _routed(monkeypatch, groq=True, openrouter=True, gemini=False)
    expected = {
        "strategist": "groq/llama-3.1-8b-instant",
        "query_rewriter": "groq/llama-3.1-8b-instant",
        "researcher": "groq/llama-3.3-70b-versatile",
        "lead_intel": "groq/llama-3.3-70b-versatile",
        "writer": "groq/llama-3.3-70b-versatile",
        "editor": "groq/llama-3.3-70b-versatile",
        "analyst": "groq/llama-3.3-70b-versatile",
        "reviewer": "groq/llama-3.3-70b-versatile",
        "eval": "groq/llama-3.3-70b-versatile",
    }
    for role, slug in expected.items():
        assert get_model(role) == slug, role


def test_routed_groq_only_keeps_per_role_tiering(monkeypatch):
    # With only the Groq key, light work still uses 8B and the reasoning/judge
    # roles must resolve to Groq 70B directly rather than pinning an absent
    # OpenRouter model and eating a failing fallback round-trip.
    _routed(monkeypatch, groq=True, openrouter=False, gemini=False)

    assert get_model("strategist") == "groq/llama-3.1-8b-instant"
    assert get_model("researcher") == "groq/llama-3.3-70b-versatile"
    assert get_model("analyst") == "groq/llama-3.3-70b-versatile"
    assert get_model("reviewer") == "groq/llama-3.3-70b-versatile"
    assert get_model("eval") == "groq/llama-3.3-70b-versatile"
    # No peer provider → no cross-provider fallback to fail against.
    assert get_fallbacks("analyst") == []
    assert get_fallbacks("reviewer") == []


def test_reasoning_avoids_unreliable_free_model(monkeypatch):
    # hy3 is $0 (cheaper than Groq 70B) but not a valid crewai primary — it
    # returns empty content — so it carries no primary caps. The reasoning role
    # resolves to the reliable Groq 70B, and hy3 is only reachable as the
    # derived cross-provider fallback.
    _routed(monkeypatch, groq=True, openrouter=True, gemini=False)

    assert get_model("analyst") == "groq/llama-3.3-70b-versatile"
    assert get_fallbacks("analyst") == ["openrouter/tencent/hy3:free"]


def test_judge_falls_back_to_generator_model_without_distinct_option(monkeypatch):
    # The judge PREFERS a model distinct from the generators, but on this key set
    # no distinct reliable model carries a judge cap, so it resolves to the same
    # Groq 70B the generators use. JUDGE_MODEL is the way to actually decouple
    # them on a single-provider deployment.
    _routed(monkeypatch, groq=True, openrouter=True, gemini=False)

    assert get_model("writer") == "groq/llama-3.3-70b-versatile"
    assert get_model("reviewer") == "groq/llama-3.3-70b-versatile"

    monkeypatch.setattr(settings, "JUDGE_MODEL", "groq/llama-3.1-8b-instant")
    assert get_model("reviewer") == "groq/llama-3.1-8b-instant"


def test_tool_use_primary_avoids_poor_tool_caller(monkeypatch):
    # The researcher drives a ReAct tool loop, so its PRIMARY must be a good
    # tool-caller (Groq 70B) even though the free model is cheaper — the free
    # model is a poor tool-caller and only reachable as a fallback leg.
    _routed(monkeypatch, groq=True, openrouter=True, gemini=False)

    assert get_model("researcher") == "groq/llama-3.3-70b-versatile"


def test_unknown_agent_raises(monkeypatch):
    _routed(monkeypatch)

    with pytest.raises(KeyError):
        get_model("nonexistent")
