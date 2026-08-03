"""Guards the retrieval pipeline's measured behaviour end to end.

Opt-in: this ingests the eval corpus into pgvector, loads the real embedder and
the real cross-encoder, and runs 72 queries through `tools.rag.retrieve`. It
needs a database (`docker compose up -d db`) and takes a couple of minutes.

    RUN_MODEL_EVALS=1 uv run pytest tests/test_retrieval_eval.py

The floors below sit deliberately under the measured numbers. This is a
regression guard, not a leaderboard: it should fire when retrieval breaks, and
stay quiet when a model version shifts a metric by a point. Tightening a floor
to whatever today's run produced would turn every unrelated dependency bump into
a failure and train everyone to ignore it.

Measured at the time of writing, Gemini embeddings + pinned sub-queries:
hit@1 0.790, hit@5 0.903, hit@10 0.968, MRR 0.846, pool recall 1.000,
coverage 0.895 ranked / 0.903 delivered, 7.8 chunks in 4.6 blocks.

The ablation tests below run every variant in `evals/retrieval_baselines.py`
and roughly triple the runtime, which is why they take their own fixture.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_MODEL_EVALS"),
    reason="ingests a corpus and loads real models; set RUN_MODEL_EVALS=1 to run",
)

EVAL_TEST_COLLECTION = "retrieval_eval_test"


@pytest.fixture(scope="module", autouse=True)
def embedding_cache_on():
    """Turn the embedding cache back on, for this file only.

    config.py disables it under pytest so a shared store cannot make "did this
    call the embedder?" assertions depend on what an earlier test warmed. No test
    here makes that kind of assertion — they measure retrieval quality — and
    embeddings are deterministic, so a warm cache cannot move a number.

    What it prevents is real: this file embeds the corpus once and the 72 queries
    once per ablation variant, which cold is a burst of roughly 270 API calls and
    trips the provider's per-minute quota mid-run. Entries land in the normal
    keyspace because they are the normal vectors for the configured model.
    """
    from unittest.mock import patch

    from config import settings
    from utils.embedding_cache import EmbeddingCache

    with patch.object(settings, "EMBEDDING_CACHE_ENABLED", True):
        cache = EmbeddingCache()

    if not cache.enabled:  # no Redis; the eval still runs, just cold
        yield
        return

    with patch("tools.rag.embedding_cache", cache):
        yield


@pytest.fixture(scope="module")
def measured():
    from evals.retrieval_eval import (
        ingest_corpus,
        run_adversarial,
        run_golden,
        summarise,
    )

    ingest_corpus(EVAL_TEST_COLLECTION)
    golden = run_golden(EVAL_TEST_COLLECTION)
    adversarial = run_adversarial(EVAL_TEST_COLLECTION)
    return summarise(golden), golden, adversarial


def test_agent_sees_an_answering_chunk_for_most_queries(measured):
    """hit@5 is the number that matters operationally: RAGTool hands the agent
    exactly 5 chunks, so a relevant chunk at rank 6 may as well not exist."""
    summary, _, _ = measured
    assert summary["hit@5"] >= 0.80, f"hit@5 fell to {summary['hit@5']:.3f}"


def test_the_answering_chunk_is_usually_ranked_first(measured):
    """MRR, not hit rate, is what moves when re-ranking degrades — a change that
    pushes the right chunk from rank 1 to rank 4 leaves hit@5 untouched."""
    summary, _, _ = measured
    assert summary["mrr"] >= 0.70, f"MRR fell to {summary['mrr']:.3f}"


def test_recall_does_not_collapse_before_reranking(measured):
    """Pool recall is the ceiling everything downstream works against. If this
    drops, the fan-out is losing chunks and no re-ranker change can recover
    them — which is a different bug from a ranking regression and needs a
    different fix, so it gets its own assertion."""
    summary, _, _ = measured
    assert summary["pool_recall"] >= 0.95, f"pool recall fell to {summary['pool_recall']:.3f}"


def test_hybrid_retrieval_contributes_more_than_the_vector_half(measured):
    """The lexical half once returned nothing at all for every question-shaped
    query, because plainto_tsquery ANDs its terms — the pool was exactly the
    vector half's 10 results, for 72 queries running. Nothing failed; hybrid
    search had simply stopped being hybrid. A mean pool at the vector limit is
    that failure's signature."""
    from tools.rag import _CANDIDATES_PER_QUERY

    summary, _, _ = measured
    assert summary["mean_pool_size"] > _CANDIDATES_PER_QUERY, (
        f"mean pool is {summary['mean_pool_size']:.1f} against a vector-half limit of "
        f"{_CANDIDATES_PER_QUERY} — the keyword half is contributing nothing"
    )


def test_neighbour_expansion_never_delivers_less_than_the_ranking(measured):
    """Expansion adds chunks around the results; it must never remove one.

    The failure it guards is a stitching or grouping bug quietly dropping a
    retrieved chunk on its way into a block — invisible in hit@k and MRR, which
    score the ranking rather than what the agent is handed."""
    summary, _, _ = measured
    assert summary["context_coverage"] >= summary["coverage@5"], (
        f"expansion delivers {summary['context_coverage']:.3f} of relevant chunks "
        f"against {summary['coverage@5']:.3f} from the ranking alone"
    )


def test_neighbour_expansion_stays_within_its_budget(measured):
    """Every search_documents call is prompt an agent pays for, several times per
    node. `_MAX_CONTEXT_CHUNKS` is the ceiling; this checks the typical case sits
    well under it rather than riding the cap."""
    from tools.rag import _MAX_CONTEXT_CHUNKS

    summary, _, _ = measured
    assert summary["mean_delivered"] <= _MAX_CONTEXT_CHUNKS
    assert summary["mean_blocks"] >= 1


def test_configured_threshold_rarely_abstains_on_answerable_queries(measured):
    """The invisible failure: documents the user uploaded go unused, the agent
    quietly falls back to the web, and nothing anywhere reports an error."""
    from config import settings
    from evals.retrieval_eval import abstention_report

    _, golden, adversarial = measured
    gate = abstention_report(golden, adversarial, settings.RAG_MIN_RERANK_SCORE)

    assert gate["false_abstention_rate"] <= 0.10, (
        f"threshold {settings.RAG_MIN_RERANK_SCORE} abstains on "
        f"{len(gate['false_abstentions'])}/{len(golden)} answerable queries"
    )


def test_configured_threshold_rejects_most_unanswerable_queries(measured):
    """The gate's one job. It shipped at -11.0 on pair-level calibration and
    rejected 1 of 10 unanswerable queries in situ — passing every isolated-pair
    assertion while doing essentially nothing in production. Only a
    best-of-pool measurement catches that, so this assertion lives here."""
    from config import settings
    from evals.retrieval_eval import abstention_report

    _, golden, adversarial = measured
    gate = abstention_report(golden, adversarial, settings.RAG_MIN_RERANK_SCORE)

    assert gate["correct_abstentions"] >= len(adversarial) * 0.6, (
        f"threshold {settings.RAG_MIN_RERANK_SCORE} rejects only "
        f"{gate['correct_abstentions']}/{len(adversarial)} unanswerable queries"
    )


@pytest.fixture(scope="module")
def ablation(measured):
    """Every variant in `retrieval_baselines`, over the corpus `measured` built."""
    from evals.retrieval_eval import compare_variants

    return {row["variant"].name: row for row in compare_variants(EVAL_TEST_COLLECTION)}


def test_the_gate_is_what_the_re_ranker_actually_buys(ablation):
    """The one column where the pipeline categorically beats naive RAG.

    Dense top-k has no abstention gate available to it — cosine similarity is not
    on the cross-encoder's scale — so it answers every unanswerable query with
    confidently-formatted, citable-looking excerpts. That is the failure that
    motivated the gate, and it is the thing the cross-encoder is genuinely in the
    pipeline for on a corpus this size."""
    assert ablation["dense"]["gate"] is None
    reranked = ablation["dense+rerank"]["gate"]
    assert reranked["correct_abstentions"] >= 0.6 * reranked["adversarial_total"]


def test_the_pipeline_does_not_fall_further_behind_naive_dense_retrieval(ablation):
    """Records an uncomfortable measurement so it cannot be quietly forgotten.

    On this corpus naive dense retrieval *outranks* production: hit@5 0.984
    against 0.903, MRR 0.930 against 0.846. 54 chunks is small enough that the
    dense half alone reaches pool recall 1.000, so the lexical fan-out can only
    add distractors and the re-ranker can only reorder an already-correct list.
    The pipeline's bet is that this inverts as a corpus grows and dense recall
    stops being perfect — a bet this harness cannot settle.

    So the assertion is on the *gap*, not on a winner: it stays quiet if the
    pipeline improves and fires if it drifts further behind the baseline, which
    would mean the fan-out has started adding noise rather than recall."""
    dense = ablation["dense"]["summary"]
    production = ablation["hybrid+rerank"]["summary"]

    gap = dense["hit@5"] - production["hit@5"]
    assert gap <= 0.15, (
        f"production trails naive dense retrieval by {gap:.3f} on hit@5 "
        f"({production['hit@5']:.3f} against {dense['hit@5']:.3f})"
    )


def test_every_variant_reaches_the_same_recall_ceiling(ablation):
    """Why the ablation reads the way it does: all three find the answer
    somewhere. With the ceiling already at 1.000 for the cheapest variant, the
    stages above it have nothing left to recover and can only lose ground."""
    for name, row in ablation.items():
        assert row["summary"]["pool_recall"] >= 0.95, (
            f"{name} pool recall fell to {row['summary']['pool_recall']:.3f}"
        )


def test_pair_level_threshold_would_barely_gate_anything(measured):
    """Regression on the reasoning, not the number. -11.0 is what you get by
    setting the threshold from `rerank_calibration.py` alone, and it is far too
    low because a retrieved pool's best chunk scores nothing like a passage
    picked to be off-topic. Keep the discrepancy executable so the pair-level
    number cannot be re-adopted on the strength of how carefully it was
    measured."""
    from evals.retrieval_eval import abstention_report

    _, golden, adversarial = measured
    gate = abstention_report(golden, adversarial, -11.0)

    assert gate["correct_abstentions"] <= 2
