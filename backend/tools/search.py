from crewai.tools import BaseTool
from tavily import TavilyClient
from config import settings
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential
from logger import logger
from utils.cache import tool_cache

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
        cached = tool_cache.get(self.name, query)
        if cached:
            logger.info("tavily_search_cache_hit", query=query)
            return cached

        res = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            include_answer=True,
        )
        tool_cache.set(self.name, query, res)
        return res

    def _run(self, query: str) -> str:
        logger.info("tavily_search_start", query=query)
        try:
            results = self._execute_search(query)
            output = []
            if results.get("answer"):
                output.append(f"**Summary:** {results['answer']}\n")
            for r in results.get("results", []):
                output.append(f"- [{r['title']}]({r['url']})\n  {r.get('content', '')[:300]}")
            return "\n".join(output) or "No search results found for this query."
        except Exception as e:
            logger.warning("tavily_search_failed", query=query, error=str(e))
            return (
                f"⚠️ Web search temporarily unavailable (Tavily: {type(e).__name__}). "
                "Continuing with available information. "
                "The final output may have fewer external sources than usual."
            )

tavily_search_tool = TavilySearchTool()
