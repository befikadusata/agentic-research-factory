from crewai.tools import BaseTool
import asyncio
from firecrawl import FirecrawlApp
from config import settings
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential
from logger import logger
from utils.cache import tool_cache
from typing import List, Dict

class FirecrawlTool(BaseTool):
    name: str = "scrape_webpage"
    description: str = (
        "Scrape the full content of a webpage and return it as clean markdown. "
        "Input: a URL string. Use this to get the full text of articles or reports found via web_search."
    )
    app: FirecrawlApp = Field(default_factory=lambda: FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY))

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
        logger.info("firecrawl_scrape_start", url=url)
        try:
            result = self._execute_scrape(url)
            content = result.get("markdown", "")
            return content[:6000] if content else "No content extracted from this page."
        except Exception as e:
            logger.warning("firecrawl_scrape_failed", url=url, error=str(e))
            return (
                f"⚠️ Page scraping unavailable for {url} (Firecrawl: {type(e).__name__}). "
                "Continuing with search result snippets instead. "
                "The analysis will rely on summary data rather than full-page content."
            )

class BatchScrapeTool(BaseTool):
    name: str = "batch_scrape_webpages"
    description: str = (
        "Scrape multiple webpages concurrently and return their clean markdown content. "
        "Input: a list of URL strings. Use this to quickly get the full text of multiple articles at once."
    )
    app: FirecrawlApp = Field(default_factory=lambda: FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY))

    async def _scrape_single(self, url: str) -> Dict:
        """Scrape a single URL with caching."""
        cached = tool_cache.get("scrape_webpage", url)
        if cached:
            logger.info("firecrawl_batch_cache_hit", url=url)
            return {"url": url, "content": cached.get("markdown", "")[:6000]}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True})
            )
            tool_cache.set("scrape_webpage", url, result)
            return {"url": url, "content": result.get("markdown", "")[:6000]}
        except Exception as e:
            logger.warning("firecrawl_batch_scrape_failed", url=url, error=str(e))
            return {"url": url, "content": f"Error: {str(e)}"}

    def _run(self, urls: List[str]) -> str:
        """Sync wrapper for the async batch scrape."""
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
            # Check if there is an existing running loop
            try:
                loop = asyncio.get_running_loop()
                # If we're here, we're in an async context, but _run is sync.
                # CrewAI often runs tools in threads, so this might be okay.
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
        return "\n---\n".join(output) or "No content extracted."

firecrawl_tool = FirecrawlTool()
batch_scrape_tool = BatchScrapeTool()
