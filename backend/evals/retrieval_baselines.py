"""Ablations of the retrieval pipeline, so each stage has to justify its cost.

`retrieval_eval.py` answers "is retrieval good?". This answers the question
underneath it: **good compared to what?** A hit@5 of 0.903 is only impressive if
plain vector search over the same corpus does worse, and until that is measured
the sub-query fan-out, the lexical half, and the cross-encoder are all being paid
for on the strength of the papers they came from.

Three retrievers, each adding one stage to the last:

| variant          | what it is                                              |
|------------------|---------------------------------------------------------|
| `dense`          | naive RAG — embed the query, take the top k by cosine    |
| `dense+rerank`   | same candidates, re-scored by the cross-encoder          |
| `hybrid+rerank`  | production `tools.rag.retrieve`                          |

Read the differences, not the rows: `dense` → `dense+rerank` is what the
cross-encoder buys, and `dense+rerank` → `hybrid+rerank` is what the lexical
half buys. Neighbour expansion is applied to every variant by the harness, so it
is not a variant here — its effect shows up in each row as `coverage@5` versus
`context_coverage`.

All three take the same candidate budget (`_CANDIDATES_PER_QUERY`) and the same
embedder, so the comparison is between the pipeline stages and nothing else.
Sub-query expansion stays pinned off for the same reproducibility reason it is
off in the harness, which also means `dense` here is the honest naive baseline:
one query, one vector search.

    uv run python -m evals.retrieval_eval --compare
"""

from dataclasses import dataclass
from typing import Callable

from config import settings
from tools.rag import (
    _CANDIDATES_PER_QUERY,
    _embed,
    _get_client,
    _reranker,
    _safe_collection,
    Candidate,
    retrieve,
)


def _dense_candidates(query: str, collection_name: str) -> list[Candidate]:
    """Top-k by cosine distance — the whole of naive RAG's retrieval.

    Scores are cosine similarity (1 - distance), which is NOT on the
    cross-encoder's scale and must never be compared to `RAG_MIN_RERANK_SCORE`.
    That is the point of the `gated` flag below: this variant has no abstention
    gate available to it, and reporting one would be inventing a number.
    """
    name = _safe_collection(collection_name)
    collection = _get_client().get_or_create_collection(
        name=name, dimension=settings.EMBEDDING_DIMENSION
    )
    [vector] = _embed([query])

    # vecs returns (id, distance, metadata) ordered by distance ascending, so the
    # order it comes back in *is* the ranking.
    records = collection.query(
        data=vector,
        limit=_CANDIDATES_PER_QUERY,
        include_metadata=True,
        include_value=True,
    )
    return [
        Candidate(chunk_id=chunk_id, metadata=metadata, score=1.0 - float(distance))
        for chunk_id, distance, metadata in records
    ]


def dense(query: str, collection_name: str) -> list[Candidate]:
    return _dense_candidates(query, collection_name)


def dense_rerank(query: str, collection_name: str) -> list[Candidate]:
    """The same candidates, re-ordered by the cross-encoder.

    Isolates re-ranking from recall: the pool is identical to `dense`, so any
    difference is the cross-encoder's alone.
    """
    candidates = _dense_candidates(query, collection_name)
    if not candidates:
        return []

    scores = _reranker().predict([(query, c.metadata.get("text", "")) for c in candidates])
    return sorted(
        (
            Candidate(chunk_id=c.chunk_id, metadata=c.metadata, score=float(score))
            for c, score in zip(candidates, scores)
        ),
        key=lambda c: c.score,
        reverse=True,
    )


def hybrid_rerank(query: str, collection_name: str) -> list[Candidate]:
    """Production. Sub-queries pinned off to match the other two."""
    return retrieve(query, collection_name, sub_queries=[query])


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    rank: Callable[[str, str], list[Candidate]]
    # Whether this variant's scores are on the cross-encoder's scale, and so
    # whether RAG_MIN_RERANK_SCORE means anything for it.
    gated: bool


VARIANTS: list[Variant] = [
    Variant("dense", "naive RAG: top-k by cosine, no re-ranking", dense, gated=False),
    Variant("dense+rerank", "same pool, cross-encoder re-ranked", dense_rerank, gated=True),
    Variant("hybrid+rerank", "production retrieve()", hybrid_rerank, gated=True),
]
