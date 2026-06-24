import json
from litellm import completion
from services.llm_router import get_completion_settings
from logger import logger


def rewrite_query(original_query: str) -> str:
    """Rewrite a user query for better vector database retrieval.
    Falls back to the original query if the LLM call fails.
    """
    prompt = (
        f"Given the user's search query: '{original_query}'\n"
        "Rewrite it to be a more comprehensive, descriptive search query suitable for a vector database retrieval system.\n"
        "Ensure it captures the core intent and any implied context.\n"
        "Return ONLY the rewritten query text."
    )
    try:
        llm = get_completion_settings("query_rewriter")
        response = completion(
            model=llm.model,
            api_key=llm.api_key,
            base_url=llm.base_url,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        return response.choices[0].message.content.strip().strip("\"'")
    except Exception as e:
        logger.warning("query_rewriter_failed", error=str(e))
        return original_query


def generate_sub_queries(original_query: str, n: int = 3) -> list[str]:
    """Generate N semantically distinct sub-queries covering different angles of the topic.
    Falls back to [original_query] on any failure.
    """
    prompt = (
        f"Given the research question: '{original_query}'\n"
        f"Generate {n} semantically distinct search sub-queries that together cover "
        "different angles, implications, or facets of the topic.\n"
        "Return ONLY a JSON array of strings, e.g.: [\"query1\", \"query2\", \"query3\"]"
    )
    try:
        llm = get_completion_settings("query_rewriter")
        response = completion(
            model=llm.model,
            api_key=llm.api_key,
            base_url=llm.base_url,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        sub_queries = json.loads(raw)
        if isinstance(sub_queries, list) and sub_queries:
            return [str(q) for q in sub_queries]
        return [original_query]
    except Exception as e:
        logger.warning("generate_sub_queries_failed", error=str(e))
        return [original_query]
