from crewai.tools import BaseTool
import uuid
import re
import httpx
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings
from logger import logger
from services.query_rewriter import generate_sub_queries
import vecs
from vecs import IndexMeasure, IndexMethod
from sqlalchemy import text as sql_text

# ---------------------------------------------------------------------------
# pgvector persistent vector store, via `vecs` (pgvector + psycopg2, no
# Supabase SDK — any Postgres with the vector extension works, including the
# one Compose runs). One collection per workspace so documents persist across
# sessions. Hybrid retrieval = HNSW vector search UNION Postgres full-text
# search, merged and re-ranked by a cross-encoder.
# ---------------------------------------------------------------------------

# Collection names are interpolated into DDL/SQL below (identifiers cannot be
# bound as parameters). They are built internally as f"workspace_{uuid}", but
# validate anyway so that stays true if a caller ever passes something else.
# Hyphens are allowed because UUIDs contain them, and they are safe inside the
# double-quoted identifiers used below; quotes and semicolons are not.
_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_collection(name: str) -> str:
    if not _COLLECTION_NAME_RE.match(name):
        raise ValueError(f"Unsafe collection name: {name!r}")
    return name

_vecs_client = None
_sentence_model = None
_reranker_model = None

def _get_client():
    global _vecs_client
    if _vecs_client is None:
        _vecs_client = vecs.create_client(settings.VECTOR_DB_URL)
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

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
    # The embedder is chosen by config ALONE, never by runtime success. A per-call
    # fallback from Gemini to the local model would store vectors from two
    # different models in the same 384-dim collection — query and document vectors
    # would no longer be comparable, silently degrading retrieval. So: if Gemini
    # is configured, it is the ONLY embedder (with retries above); a hard failure
    # raises loudly rather than quietly switching models. The local model is used
    # only when Gemini is not configured at all.
    if settings.GEMINI_API_KEY:
        return [_gemini_embed(text) for text in texts]

    model = _embedder()
    return model.encode(texts).tolist()


def _ensure_fts_index(vx, name: str) -> None:
    """GIN index backing the keyword half of hybrid retrieval.

    `vecs` only ever exposed vector indexes (IndexMethod.hnsw / .ivfflat), so
    the lexical side is plain Postgres full-text search over the chunk text in
    the metadata JSONB. The expression here must match `_keyword_search`
    exactly or the planner falls back to a sequential scan.
    """
    with vx.Session() as sess, sess.begin():
        sess.execute(
            sql_text(
                f'CREATE INDEX IF NOT EXISTS "{name}_fts_idx" ON vecs."{name}" '
                "USING GIN (to_tsvector('english', metadata->>'text'))"
            )
        )


def _keyword_search(vx, name: str, query: str, limit: int, vertical: Optional[str]):
    """Lexical half of the hybrid: ts_rank_cd over the same chunks.

    Catches exact identifiers — product names, tickers, error codes — that
    embeddings routinely miss. Returns (id, metadata) to match the shape
    `Collection.query` yields with include_value=False.
    """
    where_vertical = "AND metadata->>'vertical' = :vertical" if vertical else ""
    params = {"q": query, "limit": limit}
    if vertical:
        params["vertical"] = vertical

    with vx.Session() as sess:
        rows = sess.execute(
            sql_text(
                f"""
                SELECT id, metadata
                FROM vecs."{name}"
                WHERE to_tsvector('english', metadata->>'text')
                      @@ plainto_tsquery('english', :q)
                  {where_vertical}
                ORDER BY ts_rank_cd(
                    to_tsvector('english', metadata->>'text'),
                    plainto_tsquery('english', :q)
                ) DESC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


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

            name = _safe_collection(self.collection_name)
            vx = _get_client()
            collection = vx.get_or_create_collection(
                name=name,
                dimension=settings.EMBEDDING_DIMENSION,
            )

            query_vecs = _embed(sub_queries)

            q_filter = {"vertical": {"$eq": self.vertical}} if self.vertical else None

            # Fan-out: one vector query per sub-query plus one keyword query,
            # deduped by chunk ID. Recall is what matters here — precision is
            # the cross-encoder's job below, so the two halves are merged
            # unweighted rather than score-fused.
            seen_ids: set = set()
            merged: list = []

            def _collect(records):
                for chunk_id, metadata in records:
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        merged.append((chunk_id, metadata))

            for vec in query_vecs:
                # Records are (id, metadata) when include_value=False.
                _collect(
                    collection.query(
                        data=vec,
                        limit=10,
                        include_metadata=True,
                        include_value=False,
                        filters=q_filter,
                    )
                )

            for sq in sub_queries:
                _collect(_keyword_search(vx, name, sq, 10, self.vertical))

            if not merged:
                return "No relevant documents found."

            # Re-rank merged deduplicated pool against original query
            reranker = _reranker()
            pairs = [(query, metadata.get("text", "")) for _, metadata in merged]
            scores = reranker.predict(pairs)

            scored_results = sorted(
                zip(merged, scores), key=lambda x: x[1], reverse=True
            )
            top_results = [rec for rec, _ in scored_results[:5]]

            output = []
            for _, metadata in top_results:
                text = metadata.get("text", "No text content found.")
                source = metadata.get("source", "Unknown Source")
                page = metadata.get("page", "N/A")
                output.append(f"SOURCE: {source} (Page: {page})\n---\n{text}")

            return "\n\n================\n\n".join(output)
        except Exception as e:
            logger.warning("rag_search_failed", error=str(e))
            return f"Document search unavailable: {e}"


def ingest_documents(chunks: list[dict], collection_name: str = "session_docs", vertical: str = None):
    """Upsert text chunks into the pgvector collection with metadata."""
    logger.info("rag_ingest_start", collection=collection_name, chunks=len(chunks), vertical=vertical)
    name = _safe_collection(collection_name)
    vx = _get_client()
    collection = vx.get_or_create_collection(
        name=name,
        dimension=settings.EMBEDDING_DIMENSION,
    )

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

    # Index both retrieval paths. create_index(replace=True) is the vecs
    # default and rebuilds in place, so re-ingesting into an existing
    # collection stays correct rather than accumulating stale indexes.
    collection.create_index(
        method=IndexMethod.hnsw, measure=IndexMeasure.cosine_distance
    )
    _ensure_fts_index(vx, name)
    logger.info("rag_ingest_complete", collection=collection_name)


# rag_tool = RAGTool() # Removed to force instantiation with specific collection_name


_RAG_CITATION_RE = re.compile(r"SOURCE:\s*(.+?)\s*\(Page:\s*(.+?)\)")
# Every prompt that governs actual output (configs/prompts.yaml, agents/writer.py)
# instructs agents to cite sources as Markdown links, never the internal
# "SOURCE: ... (Page: ...)" format above — that format is only ever produced by
# RAGTool._run for internal-document search results. Restricting to http(s)
# targets excludes non-citation Markdown links (in-page anchors, relative TOC
# links) that aren't source attributions.
_MARKDOWN_CITATION_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")


def extract_citations(text: str) -> list[dict]:
    """Parse citations out of agent output. Handles both the internal RAG
    'SOURCE: <file> (Page: <N>)' format and the Markdown-link '[Title](URL)'
    format every prompt actually instructs agents to produce for web-sourced
    citations, deduped across both."""
    seen: set = set()
    citations = []

    for m in _RAG_CITATION_RE.finditer(text):
        key = (m.group(1).strip(), m.group(2).strip())
        if key not in seen:
            seen.add(key)
            citations.append({"source": key[0], "page": key[1]})

    for m in _MARKDOWN_CITATION_RE.finditer(text):
        key = (m.group(1).strip(), m.group(2).strip())
        if key not in seen:
            seen.add(key)
            citations.append({"source": key[0], "page": key[1]})

    return citations
