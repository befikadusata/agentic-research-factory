"""Retrieval eval harness: does the pipeline actually find the right chunk?

`rerank_calibration.py` measures where the cross-encoder puts a *given* pair. It
cannot tell you whether retrieval surfaces the pair in the first place, because
it never runs retrieval. This does: it ingests a fixed corpus through the real
ingest path, runs golden queries through the real `tools.rag.retrieve`, and
scores the ranking it gets back.

Run it (needs Postgres with pgvector — `docker compose up -d db`):

    uv run python -m evals.retrieval_eval

The corpus lands in a `retrieval_eval` collection in whatever `VECTOR_DB_URL`
points at, dropped and rebuilt on each run, and is left in place afterwards so
`--skip-ingest` can reuse it. It is never a workspace collection, so it cannot
collide with real documents.

## What it measures

- **hit@k** — did a chunk that answers the query land in the top k? The headline
  number, and the one that matches what the agent actually sees (k=5).
- **MRR** — one over the rank of the first answering chunk. Sensitive to
  *ordering* in a way hit@k is not: promoting the right chunk from position 4 to
  position 1 moves MRR and leaves hit@5 untouched.
- **NDCG@k** — graded, so a supporting chunk ranked above an irrelevant one
  counts for something. Uses the 2/1/0 gains defined in `retrieval_corpus`.
- **pool recall** — was the chunk anywhere in the merged candidate pool, at any
  depth? This is the number that says *which half of the pipeline is at fault*.
  A miss with the chunk in the pool is a re-ranking failure. A miss with the
  chunk absent is a recall failure, and no amount of re-ranker tuning will fix
  it — the fan-out has to change.
- **abstention behaviour** — on answerable queries, how often the gate wrongly
  refuses; on adversarial ones, how often it correctly does. This is the part
  `rerank_calibration.py` could not reach: it is the configured threshold
  measured against a corpus retrieval actually searched.

## Reproducibility

Sub-query expansion is **pinned off by default**. `generate_sub_queries` calls
an LLM at temperature 0.4 and falls back to the original query on any failure,
so with it on, two runs measure two different query sets — and in an environment
with no LLM configured it silently degrades to the pinned behaviour anyway while
still claiming to have measured expansion. Off by default means the number moves
when retrieval changes, which is what a regression harness is for. Pass
`--expand` to measure the production path end to end; the report says which was
used, because the two are not comparable.

The embedder is whatever config selects, and the report names it. Gemini and
`all-MiniLM-L6-v2` produce different retrieval, so a number carried across a
change of embedder is meaningless.

## What it does not measure

Answer quality. A chunk being retrieved is not the writer using it, and this
harness stops at the retrieval boundary on purpose — everything downstream is
LLM-mediated and needs a different instrument.
"""

import argparse
import math
from dataclasses import dataclass

from evals.retrieval_corpus import (
    ADVERSARIAL,
    CHUNKS_BY_ID,
    CORPUS,
    GOLDEN,
    Golden,
    gains_for,
)

EVAL_COLLECTION = "retrieval_eval"

# Depths reported. 5 is what RAGTool hands the agent; the rest bracket it so a
# regression shows up as movement between depths rather than a single number
# ticking down for unclear reasons.
K_VALUES = (1, 3, 5, 10)


# ── metrics ──────────────────────────────────────────────────────────────────
#
# Pure functions over a ranked list of chunk ids. No models, no database — they
# are unit-tested in tests/test_retrieval_metrics.py, because a metric that is
# quietly wrong produces confident numbers and is worse than no metric at all.


def hit_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant chunk is in the top k, else 0.0. Averaged across
    queries this is hit rate — the fraction of questions retrieval could have
    answered."""
    return 1.0 if relevant.intersection(ranked_ids[:k]) else 0.0


def reciprocal_rank(ranked_ids: list[str], relevant: set[str]) -> float:
    """1/rank of the first relevant chunk (1-indexed), 0.0 if none appears."""
    for position, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / position
    return 0.0


def dcg_at_k(ranked_ids: list[str], gains: dict[str, int], k: int) -> float:
    return sum(
        gains.get(chunk_id, 0) / math.log2(position + 1)
        for position, chunk_id in enumerate(ranked_ids[:k], start=1)
    )


def ndcg_at_k(ranked_ids: list[str], gains: dict[str, int], k: int) -> float:
    """DCG normalised by the best ordering achievable for this query.

    Ideal DCG is computed over the *labelled* gains, not over what was
    retrieved, so a query whose relevant chunk never appears scores 0 rather
    than 1 — normalising against the retrieved set would score a retriever that
    found nothing as perfect at ordering nothing.
    """
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(gain / math.log2(position + 1) for position, gain in enumerate(ideal, start=1))
    if idcg == 0:
        return 0.0
    return dcg_at_k(ranked_ids, gains, k) / idcg


# ── running ──────────────────────────────────────────────────────────────────


@dataclass
class QueryResult:
    golden: Golden
    ranked_ids: list[str]
    top_score: float
    pool_size: int

    @property
    def relevant(self) -> set[str]:
        return set(self.golden.relevant)

    @property
    def found_rank(self) -> int | None:
        """1-indexed rank of the first relevant chunk, or None."""
        for position, chunk_id in enumerate(self.ranked_ids, start=1):
            if chunk_id in self.relevant:
                return position
        return None


@dataclass
class AdversarialResult:
    query: str
    top_score: float
    pool_size: int
    top_chunk_id: str | None


def ingest_corpus(collection_name: str = EVAL_COLLECTION) -> None:
    """Load the corpus through the real ingest path, from a clean collection.

    The collection is dropped first rather than re-upserted: `ingest_documents`
    assigns a fresh uuid4 to every chunk, so re-ingesting into a live collection
    would leave the previous run's copies behind and quietly measure a corpus
    with every chunk duplicated.
    """
    from tools.rag import _get_client, ingest_documents

    vx = _get_client()
    try:
        vx.delete_collection(collection_name)
    except Exception:
        pass  # first run, or a vecs version without it — get_or_create handles it

    ingest_documents(
        [
            {
                "text": chunk.text,
                "metadata": {"source": chunk.source, "page": chunk.page, "eval_id": chunk.id},
            }
            for chunk in CORPUS
        ],
        collection_name=collection_name,
    )


def _rank(query: str, collection_name: str, expand: bool):
    from tools.rag import retrieve

    candidates = retrieve(
        query,
        collection_name,
        sub_queries=None if expand else [query],
    )
    # Chunks carry `eval_id` through ingest; anything without one is not from
    # this corpus and would silently count as an irrelevant result, so assert
    # rather than tolerate it.
    ranked_ids = []
    for candidate in candidates:
        eval_id = candidate.metadata.get("eval_id")
        assert eval_id in CHUNKS_BY_ID, f"unexpected chunk in eval collection: {eval_id!r}"
        ranked_ids.append(eval_id)

    top_score = candidates[0].score if candidates else float("-inf")
    return ranked_ids, top_score, len(candidates)


def run_golden(collection_name: str = EVAL_COLLECTION, expand: bool = False) -> list[QueryResult]:
    results = []
    for golden in GOLDEN:
        ranked_ids, top_score, pool_size = _rank(golden.query, collection_name, expand)
        results.append(QueryResult(golden, ranked_ids, top_score, pool_size))
    return results


def run_adversarial(
    collection_name: str = EVAL_COLLECTION, expand: bool = False
) -> list[AdversarialResult]:
    results = []
    for query in ADVERSARIAL:
        ranked_ids, top_score, pool_size = _rank(query, collection_name, expand)
        results.append(
            AdversarialResult(
                query=query,
                top_score=top_score,
                pool_size=pool_size,
                top_chunk_id=ranked_ids[0] if ranked_ids else None,
            )
        )
    return results


# ── aggregation ──────────────────────────────────────────────────────────────


def summarise(results: list[QueryResult]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    summary = {"queries": n}
    for k in K_VALUES:
        summary[f"hit@{k}"] = sum(hit_at_k(r.ranked_ids, r.relevant, k) for r in results) / n
        summary[f"ndcg@{k}"] = (
            sum(ndcg_at_k(r.ranked_ids, gains_for(r.golden), k) for r in results) / n
        )

    summary["mrr"] = sum(reciprocal_rank(r.ranked_ids, r.relevant) for r in results) / n
    # Anywhere in the pool at any depth — the recall ceiling re-ranking works
    # against. hit@k can never exceed this.
    summary["pool_recall"] = sum(
        hit_at_k(r.ranked_ids, r.relevant, len(r.ranked_ids)) for r in results
    ) / n
    summary["mean_pool_size"] = sum(r.pool_size for r in results) / n
    return summary


def abstention_report(
    golden_results: list[QueryResult],
    adversarial_results: list[AdversarialResult],
    threshold: float,
) -> dict:
    """The two errors the gate can make, counted separately because they are not
    symmetric: a false abstention loses a document the user uploaded and shows
    no error, while an admitted adversarial query returns chunks the agent may
    cite."""
    false_abstentions = [r for r in golden_results if r.top_score < threshold]
    admitted = [r for r in adversarial_results if r.top_score >= threshold]
    return {
        "threshold": threshold,
        "false_abstentions": false_abstentions,
        "false_abstention_rate": len(false_abstentions) / max(len(golden_results), 1),
        "correct_abstentions": len(adversarial_results) - len(admitted),
        "admitted_adversarial": admitted,
        "adversarial_total": len(adversarial_results),
    }


def threshold_sweep(
    golden_results: list[QueryResult],
    adversarial_results: list[AdversarialResult],
    candidates: list[float],
) -> list[dict]:
    """What each candidate threshold would cost, on this corpus.

    `rerank_calibration.py` sweeps thresholds over hand-written (query, passage)
    pairs — pairs someone chose. This sweeps over the scores retrieval actually
    produced for its own best candidate, which is the quantity the gate compares
    against in production. The two can disagree, and where they do, this one is
    the relevant measurement.
    """
    return [
        {
            "threshold": t,
            "false_abstentions": sum(1 for r in golden_results if r.top_score < t),
            "admitted_adversarial": sum(1 for r in adversarial_results if r.top_score >= t),
        }
        for t in sorted(candidates)
    ]


def by_kind(results: list[QueryResult]) -> dict[str, dict]:
    grouped: dict[str, list[QueryResult]] = {}
    for result in results:
        grouped.setdefault(result.golden.kind, []).append(result)
    return {kind: summarise(group) for kind, group in sorted(grouped.items())}


# ── report ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expand",
        action="store_true",
        help="use live LLM sub-query expansion (measures production; not reproducible)",
    )
    parser.add_argument(
        "--collection", default=EVAL_COLLECTION, help="vecs collection to build the corpus in"
    )
    parser.add_argument(
        "--skip-ingest", action="store_true", help="reuse the collection from a previous run"
    )
    args = parser.parse_args()

    from config import settings

    embedder = (
        f"{settings.EMBEDDING_MODEL} (Gemini)" if settings.GEMINI_API_KEY else "all-MiniLM-L6-v2 (local)"
    )

    if not args.skip_ingest:
        print(f"\ningesting {len(CORPUS)} chunks into '{args.collection}' with {embedder}...")
        ingest_corpus(args.collection)

    golden_results = run_golden(args.collection, args.expand)
    adversarial_results = run_adversarial(args.collection, args.expand)

    summary = summarise(golden_results)
    gate = abstention_report(golden_results, adversarial_results, settings.RAG_MIN_RERANK_SCORE)

    print(
        f"\nretrieval eval — {len(CORPUS)} chunks, {len(GOLDEN)} answerable queries, "
        f"{len(ADVERSARIAL)} adversarial"
    )
    print(f"  embedder:   {embedder}")
    print("  re-ranker:  cross-encoder/ms-marco-MiniLM-L-6-v2")
    print(
        "  sub-query expansion: "
        + ("live LLM (not reproducible)" if args.expand else "pinned off (reproducible)")
    )
    print(f"  mean candidate pool: {summary['mean_pool_size']:.1f} of {len(CORPUS)} chunks\n")

    for k in K_VALUES:
        print(f"  hit@{k:<3} {summary[f'hit@{k}']:.3f}    ndcg@{k:<3} {summary[f'ndcg@{k}']:.3f}")
    print(f"  MRR     {summary['mrr']:.3f}")
    print(f"  pool recall (any depth)  {summary['pool_recall']:.3f}   <- ceiling for hit@k")

    print("\n  by query kind:")
    for kind, stats in by_kind(golden_results).items():
        print(
            f"    {kind:<12} n={stats['queries']:<3} hit@5={stats['hit@5']:.3f}  "
            f"mrr={stats['mrr']:.3f}  pool recall={stats['pool_recall']:.3f}"
        )

    print(f"\n  abstention gate at RAG_MIN_RERANK_SCORE = {gate['threshold']}")
    print(
        f"    false abstentions on answerable queries: "
        f"{len(gate['false_abstentions'])}/{summary['queries']}"
    )
    print(
        f"    correct abstentions on adversarial:      "
        f"{gate['correct_abstentions']}/{gate['adversarial_total']}"
    )
    for result in gate["admitted_adversarial"]:
        print(f"      admitted ({result.top_score:>7.3f}): {result.query}  -> {result.top_chunk_id}")

    answerable_scores = sorted(r.top_score for r in golden_results)
    adversarial_scores = sorted(r.top_score for r in adversarial_results)
    print(
        f"\n    best-chunk score, answerable:  min={answerable_scores[0]:>7.3f}  "
        f"median={answerable_scores[len(answerable_scores) // 2]:>7.3f}  max={answerable_scores[-1]:>7.3f}"
    )
    print(
        f"    best-chunk score, adversarial: min={adversarial_scores[0]:>7.3f}  "
        f"median={adversarial_scores[len(adversarial_scores) // 2]:>7.3f}  max={adversarial_scores[-1]:>7.3f}"
    )

    print("\n    candidate thresholds (false abstentions / adversarial admitted):")
    sweep = threshold_sweep(
        golden_results,
        adversarial_results,
        sorted({-11.0, -10.0, -9.0, -8.0, -7.0, -6.0, -4.0, 0.0, settings.RAG_MIN_RERANK_SCORE}),
    )
    for row in sweep:
        marker = "  <- configured" if row["threshold"] == settings.RAG_MIN_RERANK_SCORE else ""
        print(
            f"      {row['threshold']:>7.2f}   {row['false_abstentions']:>2}/{len(golden_results)}"
            f"   {row['admitted_adversarial']:>2}/{len(adversarial_results)}{marker}"
        )

    misses = sorted(golden_results, key=lambda r: reciprocal_rank(r.ranked_ids, r.relevant))
    print("\n  weakest queries:")
    for result in misses[:8]:
        rank = result.found_rank
        where = f"rank {rank}" if rank else "NOT RETRIEVED"
        print(f"    [{where:>13}] ({result.golden.kind}) {result.golden.query}")
        if rank is None or rank > 5:
            print(f"                     top result was: {result.ranked_ids[0] if result.ranked_ids else '—'}")
    print()


if __name__ == "__main__":
    main()
