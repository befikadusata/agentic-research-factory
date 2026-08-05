from crewai.tools import BaseTool
import asyncio
from functools import lru_cache
from firecrawl import FirecrawlApp
from config import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from logger import logger
from utils.cache import tool_cache
from utils.source_ledger import record_retrieved_url
from tools.untrusted import wrap_untrusted
from typing import List, Dict

# Self-hosted Firecrawl authenticates nothing (USE_DB_AUTHENTICATION=false in
# docker-compose.yml), but firecrawl-py 1.5.0 raises ValueError unless *some*
# api_key is set. Send a placeholder so the self-hosted path works keyless, as
# the README promises.
_SELF_HOSTED_KEY = "self-hosted-no-auth"

# Returned instead of page content whenever scraping can't run. Phrased for the
# agent reading it: say what degraded and what to do next, not just that it broke.
_UNAVAILABLE = (
    "⚠️ Page scraping unavailable for {url} (Firecrawl: {reason}). "
    "Continuing with search result snippets instead. "
    "The analysis will rely on summary data rather than full-page content."
)


@lru_cache(maxsize=1)
def _firecrawl_app() -> FirecrawlApp:
    """Build the Firecrawl client on first use, never at import.

    `agents/researcher.py` imports this module unconditionally, and FirecrawlApp
    raises `ValueError('No API key provided')` in its constructor, so building it
    eagerly kills the import of the researcher agent — and with it every run — on
    any machine with no FIRECRAWL_API_KEY. Scraping is optional and degrades to
    search snippets, so it must never break import.

    That failure hides locally: crewai calls load_dotenv() at import, so
    firecrawl-py's os.getenv fallback finds a key in backend/.env even when
    settings has none. Only a .env that genuinely omits it — the documented
    self-hosted setup — reaches the crash.

    With neither a key nor a URL there is nothing to talk to, and the ValueError
    escapes from here, where the callers' except-blocks turn it into the normal
    "scraping unavailable" degradation.
    """
    api_key = _set(settings.FIRECRAWL_API_KEY)
    api_url = _set(settings.FIRECRAWL_API_URL)
    return FirecrawlApp(api_key=api_key or (_SELF_HOSTED_KEY if api_url else None), api_url=api_url)


def _set(value: str | None) -> str | None:
    """Normalise a blank .env value to None — `FIRECRAWL_API_KEY=` means unset."""
    return value.strip() or None if value else None


def _scraping_configured() -> bool:
    """Whether there is anything to scrape *with*: a cloud key or a self-hosted URL."""
    return bool(_set(settings.FIRECRAWL_API_KEY) or _set(settings.FIRECRAWL_API_URL))


class _FirecrawlClientMixin:
    @property
    def app(self) -> FirecrawlApp:
        """Lazily-built shared client.

        Kept as an attribute named `app` so `patch.object(tool.app, "scrape_url")`
        still works; both tools intentionally share one client.
        """
        return _firecrawl_app()


class FirecrawlTool(_FirecrawlClientMixin, BaseTool):
    name: str = "scrape_webpage"
    description: str = (
        "Scrape the full content of a webpage and return it as clean markdown. "
        "Input: a URL string. Use this to get the full text of articles or reports found via web_search."
    )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _execute_scrape(self, url: str) -> dict:
        """Inner scrape with retries — raises on failure."""
        cached = tool_cache.get(self.name, url)
        if cached:
            logger.info("firecrawl_scrape_cache_hit", url=url)
            return cached

        res = self.app.scrape_url(
            url,
            params={"formats": ["markdown"], "onlyMainContent": True}
        )
        tool_cache.set(self.name, url, res)
        return res

    def _run(self, url: str) -> str:
        # Short-circuit before @retry: with nothing configured every attempt
        # fails identically, so retrying just adds ~6s of backoff per URL.
        if not _scraping_configured():
            logger.warning("firecrawl_not_configured", url=url)
            return _UNAVAILABLE.format(url=url, reason="not configured")

        logger.info("firecrawl_scrape_start", url=url)
        try:
            result = self._execute_scrape(url)
            content = result.get("markdown", "")
            if content:
                # Ledgered only on success: the agent picked this URL, so the
                # request alone proves nothing. A page that actually returned
                # content is a source the run really retrieved.
                record_retrieved_url(url)
            return wrap_untrusted(content[:6000]) if content else "No content extracted from this page."
        except Exception as e:
            logger.warning("firecrawl_scrape_failed", url=url, error=str(e))
            return _UNAVAILABLE.format(url=url, reason=type(e).__name__)

class BatchScrapeTool(_FirecrawlClientMixin, BaseTool):
    name: str = "batch_scrape_webpages"
    description: str = (
        "Scrape multiple webpages concurrently and return their clean markdown content. "
        "Input: a list of URL strings. Use this to quickly get the full text of multiple articles at once."
    )

    async def _scrape_single(self, url: str) -> Dict:
        """Scrape a single URL with caching."""
        cached = tool_cache.get("scrape_webpage", url)
        if cached:
            logger.info("firecrawl_batch_cache_hit", url=url)
            record_retrieved_url(url)
            return {"url": url, "content": cached.get("markdown", "")[:6000]}

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True}),
                ),
                timeout=60,
            )
            tool_cache.set("scrape_webpage", url, result)
            record_retrieved_url(url)
            return {"url": url, "content": result.get("markdown", "")[:6000]}
        except (Exception, asyncio.TimeoutError) as e:
            logger.warning("firecrawl_batch_scrape_failed", url=url, error=str(e))
            return {"url": url, "content": f"Error: {str(e)}"}

    def _run(self, urls: List[str]) -> str:
        """Sync wrapper for the async batch scrape."""
        if not _scraping_configured():
            logger.warning("firecrawl_not_configured", count=len(urls) if isinstance(urls, list) else 1)
            return _UNAVAILABLE.format(url="the requested pages", reason="not configured")

        if not isinstance(urls, list):
            if isinstance(urls, str):
                if urls.startswith("[") and urls.endswith("]"):
                    try:
                        import ast
                        urls = ast.literal_eval(urls)
                    except:
                        urls = [urls]
                else:
                    urls = [urls]
        
        logger.info("firecrawl_batch_scrape_start", count=len(urls))
        
        try:
            try:
                loop = asyncio.get_running_loop()
                # A loop is already running (CrewAI may call this tool from one),
                # and _run is sync — nest_asyncio makes run_until_complete legal.
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self._async_run(urls))
            except RuntimeError:
                return asyncio.run(self._async_run(urls))
        except Exception as e:
            logger.warning("firecrawl_batch_run_error", error=str(e))
            return f"Batch scrape failed: {str(e)}"

    async def _async_run(self, urls: List[str]) -> str:
        results = await asyncio.gather(*[self._scrape_single(u) for u in urls])
        output = []
        for res in results:
            output.append(f"### Content from {res['url']}\n\n{res['content']}\n")
        return wrap_untrusted("\n---\n".join(output)) if output else "No content extracted."

firecrawl_tool = FirecrawlTool()
batch_scrape_tool = BatchScrapeTool()
