from litellm import completion
from services.llm_router import get_completion_settings, reconcile_served_model
from utils.cost_tracker import record_side_cost
from utils.json_parse import parse_json
from logger import logger


def _record_cost(response) -> None:
    """Buffer this query_rewriter litellm call's cost so the enclosing researcher
    crew node can fold it into its token accounting (the call fires inside the
    node's sync tool loop, so it can't log cost the async way itself). Best-effort
    — cost bookkeeping must never break the retrieval call it measures."""
    try:
        usage = getattr(response, "usage", None)
        record_side_cost(
            "query_rewriter",
            reconcile_served_model("query_rewriter", getattr(response, "model", None)),
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )
    except Exception as e:
        logger.warning("query_rewriter_cost_record_failed", error=str(e))


# A single-rewrite `rewrite_query()` lived here and had no caller: sub-query
# expansion below superseded it, covering ambiguity better than one rewrite
# could. Reinstating it would put an extra LLM round trip — and an extra failure
# mode — in front of a fan-out that already handles the same problem.


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
            fallbacks=list(llm.fallbacks),
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        _record_cost(response)
        sub_queries = parse_json(response.choices[0].message.content)
        if isinstance(sub_queries, list) and sub_queries:
            return [str(q) for q in sub_queries]
        return [original_query]
    except Exception as e:
        logger.warning("generate_sub_queries_failed", error=str(e))
        return [original_query]
