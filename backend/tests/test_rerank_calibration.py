"""Guards the measurement behind settings.RAG_MIN_RERANK_SCORE.

Opt-in: this loads the real cross-encoder (~90MB) and scores 34 pairs, which is
not something the normal suite should download or spend time on. Run it when
touching the threshold, the reranker model, or the calibration set:

    RUN_MODEL_EVALS=1 uv run pytest tests/test_rerank_calibration.py

What it protects is the *reasoning*, not a leaderboard number. The threshold
shipped at 0.0 on an argument about how ms-marco-MiniLM-L-6-v2 was trained, and
measurement showed that argument does not survive contact with business-document
prose — 0.0 would have hidden 9 of 12 genuinely relevant passages. These
assertions fail if that situation quietly returns.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_MODEL_EVALS"),
    reason="loads the real cross-encoder; set RUN_MODEL_EVALS=1 to run",
)


@pytest.fixture(scope="module")
def scored():
    from evals.rerank_calibration import score_pairs

    return score_pairs()


def test_configured_threshold_does_not_hide_most_relevant_passages(scored):
    """The failure mode that matters: internal documents going silently unused
    while the agent falls back to the web and nobody sees an error."""
    from config import settings
    from evals.rerank_calibration import errors_at

    relevant_total = sum(1 for label, _ in scored if label == "relevant")
    missed = errors_at(scored, settings.RAG_MIN_RERANK_SCORE)["missed_relevant"]

    assert missed <= 1, (
        f"threshold {settings.RAG_MIN_RERANK_SCORE} hides {missed}/{relevant_total} "
        "relevant passages — retrieval would abstain on documents that do answer "
        "the query, and the abstention is invisible in production"
    )


def test_configured_threshold_still_rejects_off_topic_queries(scored):
    """The gate's one job: catch 'the corpus is not about this at all'."""
    from config import settings
    from evals.rerank_calibration import errors_at

    off_topic_total = sum(1 for label, _ in scored if label == "off_topic")
    admitted = errors_at(scored, settings.RAG_MIN_RERANK_SCORE)["admitted_off_topic"]

    assert admitted <= 1, (
        f"threshold {settings.RAG_MIN_RERANK_SCORE} admits {admitted}/{off_topic_total} "
        "off-topic pairs — the gate has stopped doing the only thing it can do"
    )


def test_absolute_score_cannot_separate_relevant_from_hard_negatives(scored):
    """The finding that shaped the design: relevant and same-topic-but-wrong
    overlap, so the gate is pool-level and narrow rather than a per-chunk filter.
    If this ever stops holding — a better reranker, a different model — a real
    per-chunk relevance filter becomes possible and this design should be
    revisited rather than left in place out of habit."""
    from evals.rerank_calibration import separation

    assert separation(scored)["margin"] < 0


def test_zero_threshold_would_hide_most_relevant_passages(scored):
    """Regression on the original mistake. 0.0 reads like a principled default —
    it is the model's trained boundary on MS MARCO web text — and it is wrong
    here. Keep the evidence executable so nobody re-derives it from first
    principles and ships it again."""
    from evals.rerank_calibration import errors_at

    assert errors_at(scored, 0.0)["missed_relevant"] >= 7
