from crewai.tools import BaseTool
import uuid
import re
import httpx
from typing import Optional
from config import settings
from logger import logger
from services.query_rewriter import generate_sub_queries
import vecs

# ---------------------------------------------------------------------------
# Supabase + vecs persistent vector store
# One collection per user_id so documents persist across sessions.
# ---------------------------------------------------------------------------

_vecs_client = None
_sentence_model = None
_reranker_model = None

def _get_client():
    global _vecs_client
    if _vecs_client is None:
        _vecs_client = vecs.create_client(settings.SUPABASE_DB_URL)
    return _vecs_client

def _embedder():
    global _sentence_model
    if _sentence_model is None:
        from sentence_transformers import SentenceTransformer
        _sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _sentence_model

def _reranker():
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder
        _reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker_model

def _gemini_embed(text: str) -> list[float]:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.EMBEDDING_MODEL}:embedContent"
    payload = {
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": settings.EMBEDDING_DIMENSION,
    }
    response = httpx.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    embedding = data.get("embedding", {})
    values = embedding.get("values")
    if not values:
        raise RuntimeError("Gemini embedding response did not include values")
    return values

def _embed(texts: list[str]) -> list[list[float]]:
    if settings.GEMINI_API_KEY:
        try:
            return [_gemini_embed(text) for text in texts]
        except Exception as e:
            logger.warning("gemini_embedding_failed", error=str(e))

    model = _embedder()
    return model.encode(texts).tolist()


class RAGTool(BaseTool):
    name: str = "search_documents"
    description: str = (
        "Search through uploaded documents for relevant information. "
        "Input: a query string. Returns matching excerpts from the user's uploaded files with metadata."
    )
    collection_name: str = "default_workspace"
    vertical: Optional[str] = None

    def _run(self, query: str) -> str:
        logger.info("rag_search_start", query=query, collection=self.collection_name, vertical=self.vertical)
        try:
            sub_queries = generate_sub_queries(query)
            logger.info("rag_sub_queries", count=len(sub_queries), queries=sub_queries)

            vx = _get_client()
            collection = vx.get_or_create_collection(
                name=self.collection_name,
                dimension=settings.EMBEDDING_DIMENSION,
            )

            query_vecs = _embed(sub_queries)

            q_filter = {"vertical": {"$eq": self.vertical}} if self.vertical else None

            # Fan-out: one vecs query per sub-query, dedup by chunk ID
            seen_ids: set = set()
            merged: list = []
            for sq, vec in zip(sub_queries, query_vecs):
                candidates = collection.query(
                    data=vec,
                    limit=10,
                    include_metadata=True,
                    include_value=False,
                    query_filter=q_filter,
                    search_params={"bm25_query": sq},
                )
                for res in candidates:
                    chunk_id = res[0]
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        merged.append(res)

            if not merged:
                return "No relevant documents found."

            # Re-rank merged deduplicated pool against original query
            reranker = _reranker()
            pairs = [(query, res[2].get("text", "")) for res in merged]
            scores = reranker.predict(pairs)

            scored_results = sorted(
                zip(merged, scores), key=lambda x: x[1], reverse=True
            )
            top_results = [res for res, _ in scored_results[:5]]

            output = []
            for res in top_results:
                metadata = res[2] if len(res) > 2 else {}
                text = metadata.get("text", "No text content found.")
                source = metadata.get("source", "Unknown Source")
                page = metadata.get("page", "N/A")
                output.append(f"SOURCE: {source} (Page: {page})\n---\n{text}")

            return "\n\n================\n\n".join(output)
        except Exception as e:
            logger.warning("rag_search_failed", error=str(e))
            return f"Document search unavailable: {e}"


def ingest_documents(chunks: list[dict], collection_name: str = "session_docs", vertical: str = None):
    """Upsert text chunks into the Supabase vecs collection with metadata."""
    logger.info("rag_ingest_start", collection=collection_name, chunks=len(chunks), vertical=vertical)
    vx = _get_client()
    # Create collection and explicitly enable BM25
    collection = vx.get_or_create_collection(
        name=collection_name, 
        dimension=settings.EMBEDDING_DIMENSION,
    )
    # Enable BM25 index
    try:
        collection.create_index(index_type=vecs.IndexType.bm25)
    except Exception:
        # Index might already exist, log and continue
        logger.info("rag_bm25_index_already_exists", collection=collection_name)
    
    texts = [c["text"] for c in chunks]
    embeddings = _embed(texts)
    
    records = []
    for chunk, emb in zip(chunks, embeddings):
        record_id = str(uuid.uuid4())
        metadata = chunk["metadata"]
        metadata["text"] = chunk["text"]  # Store text in metadata for retrieval
        if vertical: # Add vertical tag if provided
            metadata["vertical"] = vertical
        records.append((record_id, emb, metadata))
    
    collection.upsert(records=records)
    # Create HNSW index for embeddings
    collection.create_index(index_type=vecs.IndexType.hnsw)
    logger.info("rag_ingest_complete", collection=collection_name)


# rag_tool = RAGTool() # Removed to force instantiation with specific collection_name


def extract_citations(text: str) -> list[dict]:
    """Parse 'SOURCE: <file> (Page: <N>)' lines into a deduped list."""
    pattern = re.compile(r"SOURCE:\s*(.+?)\s*\(Page:\s*(.+?)\)")
    seen: set = set()
    citations = []
    for m in pattern.finditer(text):
        key = (m.group(1).strip(), m.group(2).strip())
        if key not in seen:
            seen.add(key)
            citations.append({"source": key[0], "page": key[1]})
    return citations
