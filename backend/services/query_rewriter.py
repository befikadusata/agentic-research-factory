from litellm import completion
from services.llm_router import get_completion_settings

def rewrite_query(original_query: str) -> str:
    """Rewrite a user query for better vector database retrieval."""
    llm = get_completion_settings("query_rewriter")
    prompt = f"""
    Given the user's search query: '{original_query}'
    Rewrite it to be a more comprehensive, descriptive search query suitable for a vector database retrieval system.
    Ensure it captures the core intent and any implied context.
    Return ONLY the rewritten query text.
    """

    response = completion(
        model=llm.model,
        api_key=llm.api_key,
        base_url=llm.base_url,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
    )
    return response.choices[0].message.content.strip()
