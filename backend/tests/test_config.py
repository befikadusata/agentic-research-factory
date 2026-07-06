import pytest
from config import Settings, validate_config


def _settings(**overrides):
    base = {
        "DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/test",
        "BACKEND_JWT_SECRET": "test-secret",
        "NEXTAUTH_SECRET": "test-secret",
        "ENVIRONMENT": "production",
        # .env (loaded by Settings' env_file config) sets real values for
        # these in local dev — force them unset unless a test overrides them.
        "TAVILY_API_KEY": None,
        "FIRECRAWL_API_KEY": None,
        "LLAMA_CLOUD_API_KEY": None,
        "SEARXNG_URL": None,
        "FIRECRAWL_API_URL": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_config_requires_all_keys_by_default():
    s = _settings()
    with pytest.raises(RuntimeError) as exc:
        validate_config(s)
    assert "TAVILY_API_KEY" in str(exc.value)
    assert "FIRECRAWL_API_KEY" in str(exc.value)
    assert "LLAMA_CLOUD_API_KEY" in str(exc.value)


def test_validate_config_searxng_url_exempts_tavily_key():
    s = _settings(SEARXNG_URL="http://localhost:8081", LLAMA_CLOUD_API_KEY="llx-x", FIRECRAWL_API_KEY="fc-x")
    validate_config(s)  # should not raise


def test_validate_config_firecrawl_api_url_exempts_firecrawl_key():
    s = _settings(FIRECRAWL_API_URL="http://localhost:3002", TAVILY_API_KEY="tvly-x", LLAMA_CLOUD_API_KEY="llx-x")
    validate_config(s)  # should not raise


def test_validate_config_firecrawl_api_url_alone_still_requires_tavily():
    s = _settings(FIRECRAWL_API_URL="http://localhost:3002", LLAMA_CLOUD_API_KEY="llx-x")
    with pytest.raises(RuntimeError) as exc:
        validate_config(s)
    assert "TAVILY_API_KEY" in str(exc.value)
    assert "FIRECRAWL_API_KEY" not in str(exc.value)
