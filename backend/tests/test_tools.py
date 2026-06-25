import pytest
from unittest.mock import MagicMock, patch


# ── TavilySearchTool ─────────────────────────────────────────────────────────

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


# ── FirecrawlTool ─────────────────────────────────────────────────────────────

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


# ── BatchScrapeTool ───────────────────────────────────────────────────────────

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
