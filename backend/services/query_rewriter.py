from crewai import LLM
from config import settings

def rewrite_query(original_query: str) -> str:
    """Rewrite a user query for better vector database retrieval."""
    llm = LLM(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.1
    )
    
    prompt = f"""
    Given the user's search query: '{original_query}'
    Rewrite it to be a more comprehensive, descriptive search query suitable for a vector database retrieval system.
    Ensure it captures the core intent and any implied context.
    Return ONLY the rewritten query text.
    """
    
    response = llm.call(prompt)
    return response.strip()
