import re
import uuid
from dataclasses import dataclass

import httpx
import vecs
from crewai.tools import BaseTool
from sqlalchemy import text as sql_text
from tenacity import retry, stop_after_attempt, wait_exponential
from vecs import IndexMeasure, IndexMethod

from config import settings
from logger import logger
from services.query_rewriter import generate_sub_queries
from utils.embedding_cache import embedding_cache
from utils.source_ledger import canonical_url

# pgvector persistent vector store, via `vecs` (pgvector + psycopg2, no Supabase
# SDK — any Postgres with the vector extension works, including the one Compose
# runs). One collection per workspace so documents persist across sessions.
# Hybrid retrieval = HNSW vector search UNION Postgres full-text search, merged
# and re-ranked by a cross-encoder.

# Collection names are interpolated into DDL/SQL below (identifiers cannot be
# bound as parameters), so validate them even though every caller builds them
# internally as f"workspace_{uuid}". Hyphens are allowed because UUIDs contain
# them and they are safe inside the double-quoted identifiers used below;
# quotes and semicolons are not.
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

# Gemini's documented ceiling for batchEmbedContents. The API rejects anything
# larger outright ("at most 100 requests can be in one batch"), so this is a hard
# limit rather than a tuning knob.
_GEMINI_BATCH_LIMIT = 100


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _gemini_embed(texts: list[str]) -> list[list[float]]:
    """Embed up to `_GEMINI_BATCH_LIMIT` texts in one `batchEmbedContents` call.

    The retry wraps the whole batch rather than individual texts, so a 429
    re-sends up to `_GEMINI_BATCH_LIMIT` embeddings.
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if len(texts) > _GEMINI_BATCH_LIMIT:
        raise ValueError(f"batch of {len(texts)} exceeds Gemini's limit of {_GEMINI_BATCH_LIMIT}")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.EMBEDDING_MODEL}:batchEmbedContents"
    )
    payload = {
        "requests": [
            {
                # Required per sub-request, and must carry the `models/` prefix
                # even though the same model is named in the URL.
                "model": f"models/{settings.EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": settings.EMBEDDING_DIMENSION,
            }
            for text in texts
        ]
    }
    response = httpx.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    embeddings = response.json().get("embeddings") or []

    # Results are positional: a short response would pair vectors with the wrong
    # chunks and retrieval would keep working, returning the wrong documents.
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Gemini returned {len(embeddings)} embeddings for {len(texts)} inputs"
        )

    vectors = []
    for embedding in embeddings:
        values = embedding.get("values")
        if not values:
            raise RuntimeError("Gemini embedding response did not include values")
        vectors.append(values)
    return vectors


def _embedding_model_id() -> str:
    """Identity of the vector space, for cache keys.

    Provider, model, and dimension all appear because a key that ignored any of
    them would serve vectors from a different space — the mixing `_embed_uncached`
    refuses to do at runtime.
    """
    if settings.GEMINI_API_KEY:
        return f"gemini:{settings.EMBEDDING_MODEL}:{settings.EMBEDDING_DIMENSION}"
    return f"local:all-MiniLM-L6-v2:{settings.EMBEDDING_DIMENSION}"


def _embed_uncached(texts: list[str]) -> list[list[float]]:
    # The embedder is chosen by config ALONE, never by runtime success: a per-call
    # fallback from Gemini to the local model would put vectors from two different
    # models in one collection, so query and document vectors would no longer be
    # comparable. If Gemini is configured it is the only embedder, and a hard
    # failure raises rather than switching models.
    if settings.GEMINI_API_KEY:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _GEMINI_BATCH_LIMIT):
            vectors.extend(_gemini_embed(texts[start : start + _GEMINI_BATCH_LIMIT]))
        return vectors

    model = _embedder()
    return model.encode(texts).tolist()


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts, serving what the cache already holds and computing the rest.

    Duplicates within a single call are collapsed before computing: sub-query
    expansion regularly emits the same string twice, and the original query
    again when it falls back.
    """
    if not texts:
        return []

    model_id = _embedding_model_id()
    vectors = embedding_cache.get_many(model_id, texts)

    # Unique texts still needing a vector, in first-seen order.
    pending: dict[str, None] = {}
    for text, vector in zip(texts, vectors, strict=True):
        if vector is None:
            pending[text] = None

    if pending:
        pending_texts = list(pending)
        computed = _embed_uncached(pending_texts)
        by_text = dict(zip(pending_texts, computed, strict=True))
        vectors = [
            vector if vector is not None else by_text[text]
            for text, vector in zip(texts, vectors, strict=True)
        ]
        embedding_cache.set_many(model_id, list(by_text.items()))

    logger.debug(
        "embed_complete",
        requested=len(texts),
        computed=len(pending),
        cached=len(texts) - sum(1 for t in texts if t in pending),
    )
    return vectors


def _ensure_fts_index(vx, name: str) -> None:
    """GIN index backing the keyword half of hybrid retrieval.

    `vecs` exposes only vector indexes (IndexMethod.hnsw / .ivfflat), so the
    lexical side is plain Postgres full-text search over the chunk text in the
    metadata JSONB. The expression here must match `_keyword_search` exactly or
    the planner falls back to a sequential scan.
    """
    with vx.Session() as sess, sess.begin():
        sess.execute(
            sql_text(
                f'CREATE INDEX IF NOT EXISTS "{name}_fts_idx" ON vecs."{name}" '
                "USING GIN (to_tsvector('english', metadata->>'text'))"
            )
        )


def _as_any_terms(query: str) -> str:
    """Rewrite a query so the lexical half matches ANY term rather than all.

    `plainto_tsquery` ANDs every lexeme, which requires a chunk to contain every
    content word of the query — useless for the question-shaped strings agents
    send: "What does ACM-429 mean?" parses to 'acm' & '-429' & 'mean', so the one
    chunk documenting ACM-429 does not match unless it also says "mean".

    `websearch_to_tsquery` reads a bare `or` as the disjunction operator, so
    joining the words with it gives 'acm' <-> '-429' | 'mean': any term matches,
    hyphenated identifiers stay a phrase, and `ts_rank_cd` below still ranks
    chunks matching more of the query higher. It is also the one tsquery parser
    documented never to raise on arbitrary input — an all-stopword query yields
    an empty tsquery that matches nothing rather than an error.
    """
    return " or ".join(query.split())


def _ensure_neighbour_index(vx, name: str) -> None:
    """B-tree backing neighbour lookup in `expand_context`.

    Without it, pulling the chunks either side of a result is a sequential scan
    of the whole collection on every search. The expression must match
    `_fetch_neighbours` exactly.
    """
    with vx.Session() as sess, sess.begin():
        sess.execute(
            sql_text(
                f'CREATE INDEX IF NOT EXISTS "{name}_neighbour_idx" ON vecs."{name}" '
                "((metadata->>'source'), (metadata->>'ordinal'))"
            )
        )


def _keyword_search(vx, name: str, query: str, limit: int, vertical: str | None):
    """Lexical half of the hybrid: ts_rank_cd over the same chunks.

    Catches exact identifiers — product names, tickers, error codes — that
    embeddings routinely miss. Returns (id, metadata) to match the shape
    `Collection.query` yields with include_value=False.
    """
    where_vertical = "AND metadata->>'vertical' = :vertical" if vertical else ""
    params = {"q": _as_any_terms(query), "limit": limit}
    if vertical:
        params["vertical"] = vertical

    with vx.Session() as sess:
        rows = sess.execute(
            sql_text(
                f"""
                SELECT id, metadata
                FROM vecs."{name}"
                WHERE to_tsvector('english', metadata->>'text')
                      @@ websearch_to_tsquery('english', :q)
                  {where_vertical}
                ORDER BY ts_rank_cd(
                    to_tsvector('english', metadata->>'text'),
                    websearch_to_tsquery('english', :q)
                ) DESC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


# What the agent is told when internal retrieval has nothing to offer. The
# wording is the fallback mechanism: a ReAct agent chooses its next action from
# tool output, so a bare "No relevant documents found." is a dead end it may
# answer around from memory, uncited. Naming web_search makes the handoff the
# obvious next step. Both abstention paths — empty pool, and a pool whose best
# chunk misses the bar — return this.
_NO_DOCUMENTS_MESSAGE = (
    "No relevant information found in the uploaded documents for this query. "
    "The uploaded documents do not appear to cover this topic — do not infer an "
    "answer from them. Use the web_search tool to source this instead, and cite "
    "what it returns."
)


@dataclass
class Candidate:
    """One re-ranked chunk. `score` is the cross-encoder's raw logit — unbounded,
    roughly −11..+11 for this model, and only meaningful relative to the
    calibration in evals/rerank_calibration.py."""
    chunk_id: str
    metadata: dict
    score: float


# How many candidates each retrieval half pulls per sub-query, and how many
# survive to the agent. The fan-out is deliberately wider than the output:
# recall is bought cheaply here and spent by the re-ranker below.
_CANDIDATES_PER_QUERY = 10
_RESULTS_RETURNED = 5


def retrieve(
    query: str,
    collection_name: str,
    vertical: str | None = None,
    *,
    sub_queries: list[str] | None = None,
) -> list[Candidate]:
    """The retrieval pipeline proper: expand → hybrid fan-out → dedupe → re-rank.

    Returns the *whole* pool in ranked order with scores attached. The abstention
    gate and the top-5 cut are policy applied by the caller in `RAGTool._run`,
    because a rank metric (MRR, NDCG) computed over an already-truncated list
    measures the truncation rather than the ranking.

    Pass `sub_queries` to skip the LLM expansion — the eval harness pins them so
    a re-run measures retrieval rather than that day's rewrite.
    """
    if sub_queries is None:
        sub_queries = generate_sub_queries(query)
    logger.info("rag_sub_queries", count=len(sub_queries), queries=sub_queries)

    name = _safe_collection(collection_name)
    vx = _get_client()
    collection = vx.get_or_create_collection(
        name=name,
        dimension=settings.EMBEDDING_DIMENSION,
    )

    query_vecs = _embed(sub_queries)

    q_filter = {"vertical": {"$eq": vertical}} if vertical else None

    # Fan-out: one vector query per sub-query plus one keyword query, deduped by
    # chunk ID. Recall is what matters here — precision is the cross-encoder's
    # job below, so the two halves are merged unweighted rather than score-fused.
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
                limit=_CANDIDATES_PER_QUERY,
                include_metadata=True,
                include_value=False,
                filters=q_filter,
            )
        )

    for sq in sub_queries:
        _collect(_keyword_search(vx, name, sq, _CANDIDATES_PER_QUERY, vertical))

    if not merged:
        return []

    # Re-rank the merged deduplicated pool against the ORIGINAL query, not the
    # sub-queries: the sub-queries exist to widen recall, and scoring against
    # them would rank chunks by how well they answer a question nobody asked.
    reranker = _reranker()
    scores = reranker.predict([(query, metadata.get("text", "")) for _, metadata in merged])

    ranked = sorted(
        (
            Candidate(chunk_id=chunk_id, metadata=metadata, score=float(score))
            for (chunk_id, metadata), score in zip(merged, scores, strict=True)
        ),
        key=lambda c: c.score,
        reverse=True,
    )
    return ranked


# Neighbour expansion — retrieve small, read large.

@dataclass
class ContextBlock:
    """One contiguous stretch of a document, ready to hand to an agent.

    A block is one or more chunks that sit next to each other on the same page,
    stitched back into continuous prose. `chunks` holds their metadata in reading
    order — the caller needs it to know what the block actually contains.
    """
    source: str
    page: object
    text: str
    chunks: list[dict]


# Ceiling on chunks in one tool result, seeds included. `_RESULTS_RETURNED`
# results with a radius of 1 could otherwise triple the output of a call an agent
# makes several times per node. Only the expansion is budgeted; seeds are never
# dropped, so hitting the cap costs context rather than a result.
_MAX_CONTEXT_CHUNKS = 12

# Bounds on the overlap `_stitch` will believe. The splitter is configured for
# 200 characters of overlap; the probe allows twice that and refuses anything
# shorter than the minimum, because two independent chunks routinely share a few
# trailing characters by chance and splicing on that would delete real text.
_MIN_STITCH_OVERLAP = 20
_MAX_STITCH_OVERLAP = 400


def _ordinal_of(metadata: dict) -> int | None:
    """Position of a chunk within its document, or None if it predates ordinals.

    Nothing backfills older chunks, so they are returned unexpanded rather than
    treated as position 0 — which would make every one of them a neighbour of
    every other.
    """
    value = metadata.get("ordinal")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _stitch(left: str, right: str) -> str:
    """Join two adjacent chunks, dropping the overlap they share.

    Adjacent chunks repeat `chunk_overlap` characters by construction, so a
    plain concatenation makes the document appear to say the same thing twice.
    The overlap is measured rather than assumed to be the configured 200: the
    splitter cuts at separators, so the real figure varies chunk to chunk.
    """
    limit = min(len(left), len(right), _MAX_STITCH_OVERLAP)
    for n in range(limit, _MIN_STITCH_OVERLAP - 1, -1):
        if left.endswith(right[:n]):
            return left + right[n:]
    return left + "\n\n" + right


def _fetch_neighbours(vx, name: str, wanted: list[tuple[str, int]]) -> dict[tuple[str, int], dict]:
    """Look up chunks by (source, ordinal) — one query for the whole batch."""
    if not wanted:
        return {}

    clauses = []
    params: dict = {}
    for i, (source, ordinal) in enumerate(wanted):
        clauses.append(f"(metadata->>'source' = :s{i} AND metadata->>'ordinal' = :o{i})")
        params[f"s{i}"] = source
        # ->> is text, and the JSONB value is a number, so compare as text.
        params[f"o{i}"] = str(ordinal)

    with vx.Session() as sess:
        rows = sess.execute(
            sql_text(f'SELECT metadata FROM vecs."{name}" WHERE {" OR ".join(clauses)}'),
            params,
        ).fetchall()

    found: dict[tuple[str, int], dict] = {}
    for (metadata,) in rows:
        # Re-ingesting a document adds a second copy of every chunk rather than
        # replacing it (ingest assigns a fresh uuid4 per chunk), so one key can
        # match several rows. They are copies of the same text; take the first.
        found.setdefault((metadata.get("source"), _ordinal_of(metadata)), metadata)
    return found


@dataclass
class _Piece:
    """A chunk on its way into a block: its position, and why it is here."""
    source: str
    page: object
    ordinal: int | None
    metadata: dict
    rank: int | None  # rank of the result it came from; None for a neighbour


def _blocks_from(pieces: list[_Piece]) -> list[ContextBlock]:
    """Merge pieces into contiguous runs, ordered by the best result in each.

    Runs break on a gap in ordinal and on a change of page, so a block is always
    one continuous stretch of one page and can carry a single exact citation.
    Chunks with no ordinal cannot be placed relative to anything and stay alone.
    """
    runs: list[list[_Piece]] = []

    loose = [p for p in pieces if p.ordinal is None]
    placeable = [p for p in pieces if p.ordinal is not None]

    by_source: dict[str, list[_Piece]] = {}
    for piece in placeable:
        by_source.setdefault(piece.source, []).append(piece)

    for source_pieces in by_source.values():
        source_pieces.sort(key=lambda p: p.ordinal)
        current: list[_Piece] = []
        for piece in source_pieces:
            if current and (
                piece.ordinal != current[-1].ordinal + 1 or piece.page != current[-1].page
            ):
                runs.append(current)
                current = []
            current.append(piece)
        if current:
            runs.append(current)

    runs.extend([piece] for piece in loose)

    def _best_rank(run: list[_Piece]) -> int:
        return min((p.rank for p in run if p.rank is not None), default=len(pieces))

    blocks = []
    for run in sorted(runs, key=_best_rank):
        text = ""
        for i, piece in enumerate(run):
            chunk_text = piece.metadata.get("text", "")
            text = chunk_text if i == 0 else _stitch(text, chunk_text)
        blocks.append(
            ContextBlock(
                source=run[0].source,
                page=run[0].page,
                text=text,
                chunks=[p.metadata for p in run],
            )
        )
    return blocks


def expand_context(
    candidates: list[Candidate],
    collection_name: str,
    *,
    radius: int | None = None,
) -> list[ContextBlock]:
    """Widen the winning chunks into the passages they were cut out of.

    The re-ranker scores 1000-character windows because that is what it and the
    embedder can read in full, but the window that wins is often not the window
    that answers: the chunk that names a limit and the sentence stating its
    exception are one paragraph apart and two chunks apart. This pulls in
    `radius` chunks either side of each result and stitches each contiguous run
    back into one passage.

    Expansion stops at a page boundary. The page number *is* the citation here —
    it is why ingest splits page by page at all — and a passage spanning two pages
    can only be labelled with one of them. Chunks never straddle a page break, so
    a run is always wholly on one page.

    Degrades rather than fails: chunks with no ordinal, a radius of 0, and a
    neighbour lookup that raises all yield the results unexpanded.
    """
    if not candidates:
        return []

    radius = settings.RAG_NEIGHBOUR_RADIUS if radius is None else radius

    pieces = [
        _Piece(
            source=c.metadata.get("source", "Unknown Source"),
            page=c.metadata.get("page"),
            ordinal=_ordinal_of(c.metadata),
            metadata=c.metadata,
            rank=rank,
        )
        for rank, c in enumerate(candidates)
    ]

    if radius > 0:
        # Requested in rank order and interleaved by distance, so when the budget
        # binds it is the best results that got widened.
        seeded = {(p.source, p.ordinal) for p in pieces if p.ordinal is not None}
        wanted: list[tuple[str, int]] = []
        pages: dict[tuple[str, int], object] = {}
        for distance in range(1, radius + 1):
            for piece in pieces:
                if piece.ordinal is None:
                    continue
                for ordinal in (piece.ordinal - distance, piece.ordinal + distance):
                    key = (piece.source, ordinal)
                    if ordinal < 0 or key in seeded or key in pages:
                        continue
                    if len(pieces) + len(wanted) >= _MAX_CONTEXT_CHUNKS:
                        continue
                    wanted.append(key)
                    pages[key] = piece.page

        try:
            found = _fetch_neighbours(_get_client(), _safe_collection(collection_name), wanted)
        except Exception as e:
            # Expansion is an enhancement; losing it must not lose the results.
            logger.warning("rag_neighbour_lookup_failed", error=str(e))
            found = {}

        for key, metadata in found.items():
            # A neighbour on another page is a different citation, so it is not a
            # neighbour for this purpose.
            if key not in pages or metadata.get("page") != pages[key]:
                continue
            pieces.append(
                _Piece(
                    source=key[0],
                    page=metadata.get("page"),
                    ordinal=_ordinal_of(metadata),
                    metadata=metadata,
                    rank=None,
                )
            )

    return _blocks_from(pieces)


class RAGTool(BaseTool):
    name: str = "search_documents"
    description: str = (
        "Search through uploaded documents for relevant information. "
        "Input: a query string. Returns matching excerpts from the user's uploaded files with metadata."
    )
    collection_name: str = "default_workspace"
    vertical: str | None = None

    def _run(self, query: str) -> str:
        logger.info("rag_search_start", query=query, collection=self.collection_name, vertical=self.vertical)
        try:
            ranked = retrieve(query, self.collection_name, self.vertical)

            if not ranked:
                return _NO_DOCUMENTS_MESSAGE

            top_score = ranked[0].score

            # Abstain rather than return the least-bad chunks. The pool is built
            # recall-first (sub-query fan-out UNION keyword search), so it is
            # nearly always non-empty — a workspace's documents match *something*
            # lexically for almost any query — and an empty pool alone is not
            # evidence that the documents cover the question.
            #
            # The gate is on the pool's BEST score, not applied per chunk.
            # Calibration (evals/rerank_calibration.py) shows this model's
            # absolute scores separate "the corpus isn't about this" from
            # everything else, but do NOT separate "answers the question" from
            # "same topic, doesn't" — those ranges overlap almost entirely. A
            # per-chunk filter would therefore drop relevant chunks that happen
            # to score low while keeping their higher-scoring neighbours. One
            # decision for the whole pool — answer or hand off — is what the
            # scores support; ranking orders the chunks that survive.
            if top_score < settings.RAG_MIN_RERANK_SCORE:
                logger.info(
                    "rag_search_abstained",
                    candidates=len(ranked),
                    top_score=top_score,
                    threshold=settings.RAG_MIN_RERANK_SCORE,
                )
                return _NO_DOCUMENTS_MESSAGE

            kept = ranked[:_RESULTS_RETURNED]
            blocks = expand_context(kept, self.collection_name)

            output = []
            for block in blocks:
                text = block.text or "No text content found."
                source = block.source or "Unknown Source"
                # `or`, not a .get default: chunks ingested before page
                # provenance existed carry the key with a null value, so a
                # default would never fire and the citation read "Page: None".
                page = block.page or "N/A"
                output.append(f"SOURCE: {source} (Page: {page})\n---\n{text}")

            logger.info(
                "rag_search_complete",
                candidates=len(ranked),
                returned=len(kept),
                blocks=len(blocks),
                chunks_delivered=sum(len(b.chunks) for b in blocks),
                top_score=top_score,
            )
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
    
    # Position of each chunk within its own document. Assigned here rather than by
    # each parser so every ingest path gets it — docling, LlamaParse, and the eval
    # corpus alike. It relies on the caller passing a document's chunks in reading
    # order.
    next_ordinal: dict = {}

    records = []
    for chunk, emb in zip(chunks, embeddings, strict=True):
        record_id = str(uuid.uuid4())
        metadata = chunk["metadata"]
        metadata["text"] = chunk["text"]  # Store text in metadata for retrieval
        source = metadata.get("source")
        metadata["ordinal"] = next_ordinal.get(source, 0)
        next_ordinal[source] = metadata["ordinal"] + 1
        if vertical:
            metadata["vertical"] = vertical
        records.append((record_id, emb, metadata))

    collection.upsert(records=records)

    # Index all three read paths. create_index(replace=True) is the vecs
    # default and rebuilds in place, so re-ingesting into an existing
    # collection stays correct rather than accumulating stale indexes.
    collection.create_index(
        method=IndexMethod.hnsw, measure=IndexMeasure.cosine_distance
    )
    _ensure_fts_index(vx, name)
    _ensure_neighbour_index(vx, name)
    logger.info("rag_ingest_complete", collection=collection_name)


_RAG_CITATION_RE = re.compile(r"SOURCE:\s*(.+?)\s*\(Page:\s*(.+?)\)")
# Prompts (configs/prompts.yaml, agents/writer.py) instruct agents to cite as
# Markdown links; the "SOURCE: ... (Page: ...)" format above is only ever
# produced by RAGTool._run for internal-document results. Restricting to http(s)
# targets excludes Markdown links that aren't source attributions (in-page
# anchors, relative TOC links).
_MARKDOWN_CITATION_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")

# Names the standards reserve for documentation and testing, so nothing behind
# them can ever be a real source: RFC 2606 (example.com/net/org, and the
# .example/.invalid/.test TLDs) plus RFC 6761 (localhost). Agents reach for
# these when they have nothing to cite, and a fabricated citation is worse than
# a missing one — it tells the reader the claim was sourced when it wasn't.
_RESERVED_TLDS = {"example", "invalid", "test", "localhost"}


def _is_placeholder_url(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].split("@")[-1]
    host = host.split(":", 1)[0].strip("[]").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]

    labels = host.split(".")
    if labels[-1] in _RESERVED_TLDS:
        return True
    # example.com / example.org / news.example.net — the reserved second-level
    # name under any TLD. Only the registrable position counts, so a real host
    # that merely has an "example" subdomain (example.mysite.com) is kept.
    return len(labels) >= 2 and labels[-2] == "example"


def extract_citations(text: str, seen_sources: list[str] | None = None) -> list[dict]:
    """Parse citations out of agent output. Handles both the internal RAG
    'SOURCE: <file> (Page: <N>)' format and the Markdown-link '[Title](URL)'
    format prompts instruct agents to produce for web-sourced citations, deduped
    across both.

    Links to reserved placeholder domains are dropped outright: nothing can live
    behind them, so they are fabrications rather than sources.

    Pass `seen_sources` (from utils.source_ledger) to check the rest against the
    URLs the run actually retrieved. Each web citation then carries
    `verified: bool`. Unverified citations are *kept*: the ledger can't be
    complete — a link quoted inside a scraped page is a real source it never saw
    — so dropping on a miss would delete genuine citations. Without
    `seen_sources` no claim is made and the field is absent, which is also why
    RAG document citations never carry it: there is no URL to check."""
    seen: set = set()
    citations = []
    dropped: list[str] = []

    ledger = {canonical_url(u) for u in seen_sources} if seen_sources is not None else None

    for m in _RAG_CITATION_RE.finditer(text):
        key = (m.group(1).strip(), m.group(2).strip())
        if key not in seen:
            seen.add(key)
            citations.append({"source": key[0], "page": key[1]})

    for m in _MARKDOWN_CITATION_RE.finditer(text):
        key = (m.group(1).strip(), m.group(2).strip())
        if key in seen:
            continue
        seen.add(key)
        if _is_placeholder_url(key[1]):
            dropped.append(key[1])
            continue
        citation = {"source": key[0], "page": key[1]}
        if ledger is not None:
            citation["verified"] = canonical_url(key[1]) in ledger
        citations.append(citation)

    if dropped:
        # Worth surfacing: the agent had nothing to cite and papered over it.
        logger.warning("citation_placeholder_dropped", count=len(dropped), urls=dropped[:5])

    unverified = [c["page"] for c in citations if c.get("verified") is False]
    if unverified:
        # Not necessarily fabricated, but the run has no record of fetching it.
        logger.warning("citation_unverified", count=len(unverified), urls=unverified[:5])

    return citations
