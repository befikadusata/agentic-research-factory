from crewai.tools import BaseTool
import httpx
from tavily import TavilyClient
from config import settings
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential
from logger import logger
from utils.cache import tool_cache
from utils.source_ledger import record_retrieved_url
from tools.untrusted import wrap_untrusted

class SearxngSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current information. Input: a search query string. "
        "Returns a list of relevant results with titles, URLs, and content snippets."
    )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _execute_search(self, query: str) -> dict:
        """Inner search with retries — raises on failure."""
        cached = tool_cache.get("web_search:searxng", query)
        if cached:
            logger.info("searxng_search_cache_hit", query=query)
            return cached

        resp = httpx.get(
            f"{settings.SEARXNG_URL.rstrip('/')}/search",
            params={"q": query, "format": "json"},
            timeout=30,
        )
        resp.raise_for_status()
        res = resp.json()
        tool_cache.set("web_search:searxng", query, res)
        return res

    def _run(self, query: str) -> str:
        logger.info("searxng_search_start", query=query)
        try:
            results = self._execute_search(query)
            output = []
            # 4 results × 150-char snippets (was 8 × 300): search output persists
            # in the researcher's ReAct context across iterations, so trimming it
            # here compounds — keeps the pass under Groq's free 12K tokens/min.
            for r in results.get("results", [])[:4]:
                # Ledger only the results the agent is actually shown, so a
                # citation counts as verified when the run really saw it.
                record_retrieved_url(r.get("url", ""))
                output.append(f"- [{r.get('title', '')}]({r.get('url', '')})\n  {r.get('content', '')[:150]}")
            return wrap_untrusted("\n".join(output)) if output else "No search results found for this query."
        except Exception as e:
            logger.warning("searxng_search_failed", query=query, error=str(e))
            return (
                f"⚠️ Web search temporarily unavailable (SearXNG: {type(e).__name__}). "
                "Continuing with available information. "
                "The final output may have fewer external sources than usual."
            )

class TavilySearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current information. Input: a search query string. "
        "Returns a list of relevant results with titles, URLs, and content snippets."
    )
    client: TavilyClient = Field(default_factory=lambda: TavilyClient(api_key=settings.TAVILY_API_KEY))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _execute_search(self, query: str) -> dict:
        """Inner search with retries — raises on failure."""
        cached = tool_cache.get("web_search:tavily", query)
        if cached:
            logger.info("tavily_search_cache_hit", query=query)
            return cached

        res = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            include_answer=True,
        )
        tool_cache.set("web_search:tavily", query, res)
        return res

    def _run(self, query: str) -> str:
        logger.info("tavily_search_start", query=query)
        try:
            results = self._execute_search(query)
            output = []
            if results.get("answer"):
                output.append(f"**Summary:** {results['answer']}\n")
            for r in results.get("results", []):
                record_retrieved_url(r.get("url", ""))
                output.append(f"- [{r['title']}]({r['url']})\n  {r.get('content', '')[:300]}")
            return wrap_untrusted("\n".join(output)) if output else "No search results found for this query."
        except Exception as e:
            logger.warning("tavily_search_failed", query=query, error=str(e))
            return (
                f"⚠️ Web search temporarily unavailable (Tavily: {type(e).__name__}). "
                "Continuing with available information. "
                "The final output may have fewer external sources than usual."
            )

tavily_search_tool = SearxngSearchTool() if settings.SEARXNG_URL else TavilySearchTool()
