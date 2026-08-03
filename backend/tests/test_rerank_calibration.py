"""Guards what the cross-encoder's absolute scores can and cannot tell you.

Opt-in: this loads the real cross-encoder (~90MB) and scores 34 pairs, which is
not something the normal suite should download or spend time on. Run it when
touching the reranker model or the calibration set:

    RUN_MODEL_EVALS=1 uv run pytest tests/test_rerank_calibration.py

What it protects is the *reasoning*, not a leaderboard number. The threshold
shipped at 0.0 on an argument about how ms-marco-MiniLM-L-6-v2 was trained, and
measurement showed that argument does not survive contact with business-document
prose — 0.0 would have hidden 9 of 12 genuinely relevant passages.

This file no longer *sets* `RAG_MIN_RERANK_SCORE`, and the change is worth
stating plainly because it looks like a retreat and is not. These pairs measure
the score of a chosen (query, passage) couple. The gate compares against the
best chunk retrieval found anywhere in the corpus, which is a different and much
higher quantity — so a threshold read off this distribution lands far too low,
as `evals/retrieval_eval.py` demonstrated by rejecting 1 of 10 unanswerable
queries at -11.0. The threshold is set there, against the pipeline, and
`tests/test_retrieval_eval.py` guards it. What survives here is what pairs are
genuinely evidence for: the shape of the model's score distribution on this kind
of prose, and the overlap that rules out a per-chunk relevance filter.
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


def test_pair_scores_are_more_pessimistic_than_the_gate_they_informed(scored):
    """Why the threshold is not set from this file.

    At the configured threshold several individually relevant passages score
    below the bar. Read as a prediction about production that says retrieval
    abstains on answerable queries — and it is wrong: the pipeline abstains on
    1 of 62. The gate never sees a passage in isolation. It sees the best of a
    recall-first pool, and best-of-pool runs far above the score any single
    passage earns on its own.

    This assertion exists so the discrepancy is recorded rather than
    rediscovered as a bug. If it ever stops holding — if pair scores and
    best-of-pool scores converge — then this file could set the threshold again,
    and that would be worth knowing.
    """
    from config import settings
    from evals.rerank_calibration import errors_at

    missed = errors_at(scored, settings.RAG_MIN_RERANK_SCORE)["missed_relevant"]

    assert missed >= 2, (
        f"pair-level and pipeline-level measurements have converged: threshold "
        f"{settings.RAG_MIN_RERANK_SCORE} now hides only {missed} isolated relevant "
        "passages. Re-check whether the pipeline eval and this file still disagree "
        "before trusting either alone."
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
