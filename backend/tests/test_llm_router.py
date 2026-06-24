from config import settings
from services.llm_router import get_completion_settings, get_model


def test_get_model_uses_legacy_override(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "legacy/model")

    assert get_model("researcher") == "legacy/model"


def test_get_completion_settings_uses_provider_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")

    llm = get_completion_settings("analyst")

    assert llm.model == settings.ANALYST_MODEL
    assert llm.api_key == "openrouter-test-key"


def test_get_completion_settings_treats_raw_openrouter_slugs_as_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    monkeypatch.setattr(settings, "RESEARCHER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")

    llm = get_completion_settings("researcher")

    assert llm.model == "meta-llama/llama-3.3-70b-instruct:free"
    assert llm.api_key == "openrouter-test-key"
