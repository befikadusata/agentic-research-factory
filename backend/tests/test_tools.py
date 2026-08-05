import pytest
from unittest.mock import MagicMock, patch


def _make_tavily_response(answer: str = "summary", results: list = None):
    return {
        "answer": answer,
        "results": results or [
            {"title": "Result 1", "url": "http://a.com", "content": "content A"},
        ],
    }


def test_tavily_search_success():
    from tools.search import TavilySearchTool

    tool = TavilySearchTool()
    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool.client, "search", return_value=_make_tavily_response()):
            result = tool._run("AI trends")

    assert "summary" in result
    assert "Result 1" in result
    assert "http://a.com" in result


def test_tavily_search_cache_hit_skips_api():
    from tools.search import TavilySearchTool

    tool = TavilySearchTool()
    cached = _make_tavily_response(answer="cached answer")

    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = cached
        with patch.object(tool.client, "search") as mock_search:
            result = tool._run("cached query")
            mock_search.assert_not_called()

    assert "cached answer" in result


def test_tavily_search_failure_returns_degradation_string():
    from tools.search import TavilySearchTool

    tool = TavilySearchTool()
    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool, "_execute_search", side_effect=Exception("Tavily down")):
            result = tool._run("failing query")

    assert "⚠️" in result
    assert "unavailable" in result.lower()


def test_tavily_search_no_results_returns_fallback():
    from tools.search import TavilySearchTool

    tool = TavilySearchTool()
    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool.client, "search", return_value={"answer": None, "results": []}):
            result = tool._run("empty query")

    assert result == "No search results found for this query."


def test_tavily_search_uses_provider_scoped_cache_key():
    """TavilySearchTool and SearxngSearchTool both have name == "web_search", so
    caching keyed on `self.name` collides between providers. Cache calls must use
    a provider-specific namespace."""
    from tools.search import TavilySearchTool

    tool = TavilySearchTool()
    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool.client, "search", return_value=_make_tavily_response()):
            tool._run("AI trends")

    mock_cache.get.assert_called_with("web_search:tavily", "AI trends")
    mock_cache.set.assert_called_with("web_search:tavily", "AI trends", _make_tavily_response())


def _make_searxng_response(results: list = None):
    return {
        "results": results or [
            {"title": "Result 1", "url": "http://a.com", "content": "content A"},
        ],
    }


@pytest.fixture
def searxng_url():
    """Keep SearXNG unit tests independent from developer and CI environments."""
    with patch("tools.search.settings.SEARXNG_URL", "http://searxng.test"):
        yield


def test_searxng_search_success(searxng_url):
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_searxng_response()
    mock_resp.raise_for_status.return_value = None

    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("tools.search.httpx.get", return_value=mock_resp):
            result = tool._run("AI trends")

    assert "Result 1" in result
    assert "http://a.com" in result


def test_searxng_search_cache_hit_skips_api(searxng_url):
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    cached = _make_searxng_response(results=[{"title": "Cached", "url": "http://b.com", "content": "c"}])

    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = cached
        with patch("tools.search.httpx.get") as mock_get:
            result = tool._run("cached query")
            mock_get.assert_not_called()

    assert "Cached" in result


def test_searxng_search_failure_returns_degradation_string(searxng_url):
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool, "_execute_search", side_effect=Exception("SearXNG down")):
            result = tool._run("failing query")

    assert "⚠️" in result
    assert "unavailable" in result.lower()


def test_searxng_search_no_results_returns_fallback(searxng_url):
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None

    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("tools.search.httpx.get", return_value=mock_resp):
            result = tool._run("empty query")

    assert result == "No search results found for this query."


def test_searxng_search_uses_provider_scoped_cache_key(searxng_url):
    """Same as the Tavily-side test above, but for SearXNG — the two providers
    must never read/write each other's cached results."""
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_searxng_response()
    mock_resp.raise_for_status.return_value = None

    with patch("tools.search.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("tools.search.httpx.get", return_value=mock_resp):
            tool._run("AI trends")

    mock_cache.get.assert_called_with("web_search:searxng", "AI trends")
    mock_cache.set.assert_called_with("web_search:searxng", "AI trends", _make_searxng_response())


def test_firecrawl_scrape_success():
    from tools.scraper import FirecrawlTool

    tool = FirecrawlTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool.app, "scrape_url", return_value={"markdown": "# Article\n\nContent here."}):
            result = tool._run("http://example.com/article")

    assert "# Article" in result
    assert "Content here" in result


def test_firecrawl_scrape_cache_hit_skips_api():
    from tools.scraper import FirecrawlTool

    tool = FirecrawlTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = {"markdown": "cached content"}
        with patch.object(tool.app, "scrape_url") as mock_scrape:
            result = tool._run("http://example.com")
            mock_scrape.assert_not_called()

    assert "cached content" in result


def test_firecrawl_scrape_failure_returns_degradation_string():
    from tools.scraper import FirecrawlTool

    tool = FirecrawlTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool, "_execute_scrape", side_effect=Exception("Firecrawl down")):
            result = tool._run("http://failing.com")

    assert "⚠️" in result
    assert "unavailable" in result.lower()


def test_firecrawl_no_markdown_returns_fallback():
    from tools.scraper import FirecrawlTool

    tool = FirecrawlTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(tool.app, "scrape_url", return_value={"markdown": ""}):
            result = tool._run("http://empty.com")

    assert result == "No content extracted from this page."


@pytest.mark.asyncio
async def test_batch_scrape_fetches_multiple_urls():
    from tools.scraper import BatchScrapeTool

    batch = BatchScrapeTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(batch.app, "scrape_url", return_value={"markdown": "content"}):
            result = await batch._async_run(["http://a.com", "http://b.com"])

    assert "http://a.com" in result
    assert "http://b.com" in result
    assert "content" in result


@pytest.mark.asyncio
async def test_batch_scrape_single_url_failure_includes_error():
    from tools.scraper import BatchScrapeTool

    batch = BatchScrapeTool()
    with patch("tools.scraper.tool_cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch.object(batch.app, "scrape_url", side_effect=Exception("failed")):
            result = await batch._async_run(["http://fail.com"])

    assert "http://fail.com" in result
    assert "Error" in result


# Firecrawl configuration / import safety. Scraping is optional: docker-compose
# puts self-hosted Firecrawl behind the "scraping" profile and a plain
# `docker compose up` skips it. So importing tools.scraper — which
# agents/researcher.py does unconditionally — must never need Firecrawl config;
# building the client eagerly raises ValueError('No API key provided') and takes
# every run down with it.


@pytest.fixture
def firecrawl_env(monkeypatch):
    """Set FIRECRAWL_* on settings and reset the cached client around the test."""
    from config import settings
    from tools import scraper

    def apply(api_key, api_url):
        monkeypatch.setattr(settings, "FIRECRAWL_API_KEY", api_key)
        monkeypatch.setattr(settings, "FIRECRAWL_API_URL", api_url)
        scraper._firecrawl_app.cache_clear()

    yield apply
    scraper._firecrawl_app.cache_clear()


def test_self_hosted_firecrawl_needs_no_api_key(firecrawl_env):
    """docker-compose runs Firecrawl with USE_DB_AUTHENTICATION=false.

    firecrawl-py refuses to construct without *some* key, so a placeholder
    stands in — otherwise the documented keyless self-hosted path can't work.
    """
    from tools import scraper

    firecrawl_env(None, "http://firecrawl-api:3002")
    app = scraper._firecrawl_app()

    assert app.api_url == "http://firecrawl-api:3002"
    assert app.api_key == scraper._SELF_HOSTED_KEY


def test_real_api_key_is_not_replaced_by_the_placeholder(firecrawl_env):
    from tools import scraper

    firecrawl_env("fc-real-key", "http://firecrawl-api:3002")

    assert scraper._firecrawl_app().api_key == "fc-real-key"


def test_unconfigured_scrape_degrades_instead_of_raising(firecrawl_env):
    from tools.scraper import FirecrawlTool

    firecrawl_env(None, None)
    result = FirecrawlTool()._run("http://example.com")

    assert "⚠️" in result
    assert "unavailable" in result.lower()


def test_unconfigured_batch_scrape_degrades_instead_of_raising(firecrawl_env):
    from tools.scraper import BatchScrapeTool

    firecrawl_env(None, None)
    result = BatchScrapeTool()._run(["http://example.com"])

    assert "⚠️" in result
    assert "unavailable" in result.lower()


def test_researcher_agent_imports_without_any_firecrawl_config(tmp_path):
    """The regression itself: a clean interpreter with no Firecrawl config at all.

    Subprocess, because the failure was at *import* time and tools.scraper is
    already imported in this one.

    Getting this to actually fail against the bug takes care. crewai calls
    load_dotenv() when imported, and load_dotenv walks *up* the tree — from
    anywhere inside the repo it finds backend/.env and hands a developer's real
    key to firecrawl-py's os.getenv fallback, hiding the crash. That is why the
    bug survived local use. So run from a tmp_path outside the repo with a
    minimal .env: scrubbing os.environ alone is not enough.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    # Only what Settings requires to construct — deliberately no FIRECRAWL_*.
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/unused\n"
        "BACKEND_JWT_SECRET=dummy-secret\n"
    )

    env = {k: v for k, v in os.environ.items() if not k.startswith("FIRECRAWL_")}
    env["PYTHONPATH"] = str(backend)
    env.pop("TESTING", None)  # would redirect DATABASE_URL at import

    proc = subprocess.run(
        [sys.executable, "-c", "import agents.researcher; print('ok')"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, f"researcher import failed:\n{proc.stderr[-2000:]}"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_firecrawl_config_counts_as_unconfigured(firecrawl_env, blank):
    """`FIRECRAWL_API_URL=` in a .env is unset, not a self-hosted endpoint."""
    from tools.scraper import FirecrawlTool

    firecrawl_env(blank, blank)
    result = FirecrawlTool()._run("http://example.com")

    assert "unavailable" in result.lower()
