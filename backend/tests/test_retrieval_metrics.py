"""Unit tests for the retrieval eval's metrics and golden set.

These run in the normal suite: they touch no model and no database, only the
arithmetic and the data. That is deliberate. A retrieval harness reports numbers
nobody can check by eye — nothing about "NDCG@5 = 0.813" looks wrong — so a
mistake in the metric silently produces confident nonsense, and every decision
made from it inherits the error. The gains here are hand-computed.

The end-to-end measurement (does the pipeline actually find the chunk) is in
tests/test_retrieval_eval.py, behind RUN_MODEL_EVALS.
"""
import math

import pytest

from evals.retrieval_eval import (
    coverage_at_k,
    dcg_at_k,
    hit_at_k,
    ndcg_at_k,
    reciprocal_rank,
)


# ── hit@k ────────────────────────────────────────────────────────────────────

def test_hit_at_k_finds_relevant_within_cutoff():
    assert hit_at_k(["a", "b", "c"], {"c"}, 3) == 1.0


def test_hit_at_k_ignores_relevant_beyond_cutoff():
    """The whole point of a cutoff: RAGTool hands the agent 5 chunks, so a
    relevant chunk at rank 6 is not something the agent ever sees."""
    assert hit_at_k(["a", "b", "c"], {"c"}, 2) == 0.0


def test_hit_at_k_is_binary_not_a_count():
    """Two relevant chunks in the top 3 is still one query answered."""
    assert hit_at_k(["a", "b", "c"], {"a", "b"}, 3) == 1.0


def test_hit_at_k_zero_when_nothing_relevant_retrieved():
    assert hit_at_k(["a", "b"], {"z"}, 5) == 0.0


def test_hit_at_k_handles_short_ranking():
    """k larger than the pool must not error — pool recall calls it with
    k = len(ranked)."""
    assert hit_at_k(["a"], {"a"}, 10) == 1.0
    assert hit_at_k([], {"a"}, 10) == 0.0


# ── coverage@k ───────────────────────────────────────────────────────────────

def test_coverage_counts_how_many_relevant_chunks_arrived():
    """Where hit@k stops at one, this is the difference between half an answer
    and a whole one — the question a multi-chunk query actually asks."""
    assert coverage_at_k(["a", "x", "b"], {"a", "b"}, 3) == 1.0
    assert coverage_at_k(["a", "x", "y"], {"a", "b"}, 3) == pytest.approx(0.5)


def test_coverage_respects_the_cutoff():
    assert coverage_at_k(["a", "x", "b"], {"a", "b"}, 2) == pytest.approx(0.5)


def test_coverage_agrees_with_hit_when_there_is_one_relevant_chunk():
    for ranked in (["a", "b"], ["b", "a"], ["b", "c"]):
        assert coverage_at_k(ranked, {"a"}, 2) == hit_at_k(ranked, {"a"}, 2)


def test_coverage_of_nothing_relevant_is_zero_not_a_division_error():
    assert coverage_at_k(["a"], set(), 5) == 0.0


# ── MRR ──────────────────────────────────────────────────────────────────────

def test_reciprocal_rank_is_one_for_first_position():
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0


def test_reciprocal_rank_uses_one_indexed_rank():
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_reciprocal_rank_takes_the_first_relevant_only():
    """Not the best one, the first one — that is what 'reciprocal rank' means,
    and it is why MRR moves when ordering improves and hit@k does not."""
    assert reciprocal_rank(["x", "a", "b"], {"a", "b"}) == pytest.approx(0.5)


def test_reciprocal_rank_zero_when_absent():
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


# ── NDCG ─────────────────────────────────────────────────────────────────────

def test_dcg_discounts_by_log2_of_rank_plus_one():
    # gains 2 at rank 1 and 1 at rank 2 -> 2/log2(2) + 1/log2(3)
    expected = 2 / math.log2(2) + 1 / math.log2(3)
    assert dcg_at_k(["a", "b"], {"a": 2, "b": 1}, 5) == pytest.approx(expected)


def test_ndcg_is_one_for_the_ideal_ordering():
    assert ndcg_at_k(["a", "b", "c"], {"a": 2, "b": 1}, 3) == pytest.approx(1.0)


def test_ndcg_penalises_a_graded_inversion():
    """Ranking the supporting chunk above the answering one is worse but not
    zero — the distinction binary hit rate cannot express, and the reason NDCG
    is reported at all."""
    ideal = ndcg_at_k(["a", "b"], {"a": 2, "b": 1}, 5)
    inverted = ndcg_at_k(["b", "a"], {"a": 2, "b": 1}, 5)
    assert ideal == pytest.approx(1.0)
    assert 0.0 < inverted < ideal


def test_ndcg_normalises_against_labels_not_against_what_was_retrieved():
    """A retriever that found nothing relevant must score 0, not 1. Normalising
    by the best ordering *of the retrieved list* would call a pipeline that
    returned pure noise perfectly ordered noise."""
    assert ndcg_at_k(["x", "y", "z"], {"a": 2}, 3) == 0.0


def test_ndcg_ideal_is_capped_at_k():
    """With 3 relevant chunks and k=1, retrieving one of them at rank 1 is a
    perfect result at that depth — the ideal DCG must be truncated to k too, or
    a perfect ranking scores below 1 and every number shifts down."""
    assert ndcg_at_k(["a"], {"a": 2, "b": 2, "c": 2}, 1) == pytest.approx(1.0)


def test_ndcg_zero_when_no_labels():
    assert ndcg_at_k(["a"], {}, 5) == 0.0


# ── golden set integrity ─────────────────────────────────────────────────────
#
# The metrics can be perfect and the eval still meaningless if the labels point
# at chunks that do not exist — every such query scores 0 and drags the mean
# down for a reason no report would explain.

def test_corpus_ids_are_unique():
    from evals.retrieval_corpus import CORPUS

    ids = [chunk.id for chunk in CORPUS]
    assert len(ids) == len(set(ids))


def test_every_golden_label_points_at_a_real_chunk():
    from evals.retrieval_corpus import CHUNKS_BY_ID, GOLDEN

    for golden in GOLDEN:
        for chunk_id in (*golden.relevant, *golden.partial):
            assert chunk_id in CHUNKS_BY_ID, f"{golden.query!r} labels unknown chunk {chunk_id!r}"


def test_every_golden_query_has_at_least_one_answering_chunk():
    from evals.retrieval_corpus import GOLDEN

    for golden in GOLDEN:
        assert golden.relevant, f"{golden.query!r} has no relevant chunk"


def test_relevant_and_partial_do_not_overlap():
    """A chunk graded both 2 and 1 would take the 2 silently; better to catch
    the contradiction than to let the label be decided by dict ordering."""
    from evals.retrieval_corpus import GOLDEN

    for golden in GOLDEN:
        assert not set(golden.relevant) & set(golden.partial), golden.query


def test_golden_set_meets_its_minimum_size():
    """50 is the floor this harness was built to. Below it the per-kind slices
    stop being readable and a single query moves the headline by 2%."""
    from evals.retrieval_corpus import GOLDEN

    assert len(GOLDEN) >= 50


def test_golden_queries_are_unique():
    from evals.retrieval_corpus import GOLDEN

    queries = [golden.query for golden in GOLDEN]
    assert len(queries) == len(set(queries))


def test_adversarial_queries_have_no_answer_in_the_corpus():
    """Not a semantic check — a guard against someone adding an adversarial
    query that a corpus chunk plainly answers, which would make a correct
    abstention look like a failure."""
    from evals.retrieval_corpus import ADVERSARIAL, GOLDEN

    answerable = {golden.query for golden in GOLDEN}
    assert not answerable & set(ADVERSARIAL)
    assert len(ADVERSARIAL) >= 5
