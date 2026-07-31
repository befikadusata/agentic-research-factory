"""
Tests for grounding citations in what a run actually retrieved.

A live run cited marketresearchreport.com, enterprise-search.com and
dataqualityreport.com — plausible hostnames it never visited. Placeholder
filtering can't catch those; only comparing against the retrieved sources can.
"""
import pytest

from utils.source_ledger import (
    canonical_url,
    record_retrieved_url,
    reset_seen_sources,
    take_seen_sources,
)
from tools.rag import extract_citations


@pytest.fixture(autouse=True)
def clean_ledger():
    reset_seen_sources()
    yield
    reset_seen_sources()


# ── canonical_url ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("http://onyx.app/a", "https://onyx.app/a"),          # scheme
    ("https://www.onyx.app/a", "https://onyx.app/a"),      # www
    ("https://onyx.app/a/", "https://onyx.app/a"),         # trailing slash
    ("https://ONYX.app/a", "https://onyx.app/a"),          # host case
    ("https://onyx.app:443/a", "https://onyx.app/a"),      # default port
    ("https://onyx.app/a#intro", "https://onyx.app/a"),    # fragment
    ("https://onyx.app/a?utm_source=x", "https://onyx.app/a"),   # tracking param
    ("https://onyx.app/a?b=2&c=3", "https://onyx.app/a?c=3&b=2"),  # param order
])
def test_canonical_url_treats_equivalent_forms_as_one(a, b):
    assert canonical_url(a) == canonical_url(b)


@pytest.mark.parametrize("a,b", [
    ("https://onyx.app/a", "https://onyx.app/b"),           # path matters
    ("https://onyx.app/a?id=1", "https://onyx.app/a?id=2"),  # real params matter
    ("https://onyx.app/a", "https://onyx.dev/a"),            # host matters
    # `ref` is meaningful on GitHub and friends, so it is deliberately not
    # treated as tracking — over-normalising would let a fabricated URL match.
    ("https://github.com/x?ref=main", "https://github.com/x?ref=dev"),
])
def test_canonical_url_keeps_meaningful_differences(a, b):
    assert canonical_url(a) != canonical_url(b)


def test_canonical_url_survives_a_malformed_url():
    """Bad authorities must not raise — this runs inside every tool call."""
    assert canonical_url("https://host:notaport/path")
    assert canonical_url("") == ""


# ── the ledger ────────────────────────────────────────────────────────────────

def test_ledger_records_canonically_and_deduplicates():
    record_retrieved_url("https://www.onyx.app/leaderboard/")
    record_retrieved_url("http://onyx.app/leaderboard?utm_source=news")
    assert take_seen_sources() == ["onyx.app/leaderboard"]


def test_reset_clears_the_previous_runs_sources():
    """Celery reuses worker processes; without this a run would verify its
    citations against sources a different run retrieved."""
    record_retrieved_url("https://leaked.example-real.com/a")
    reset_seen_sources()
    assert take_seen_sources() == []


def test_reset_can_seed_from_an_earlier_segment():
    """Research retrieves the sources; the write segment, a separate Celery task
    in a fresh process, is where the report's citations get extracted."""
    reset_seen_sources(["onyx.app/leaderboard"])
    record_retrieved_url("https://huggingface.co/blog/x")
    assert take_seen_sources() == ["huggingface.co/blog/x", "onyx.app/leaderboard"]


def test_record_never_raises_on_junk():
    record_retrieved_url(None)
    record_retrieved_url("")
    record_retrieved_url("https://host:notaport/x")
    take_seen_sources()  # must not blow up


# ── extract_citations grounding ───────────────────────────────────────────────

REAL = "https://onyx.app/self-hosted-llm-leaderboard"
FAKE = "https://www.dataqualityreport.com/rag-data-requirements"


def test_citations_are_flagged_against_the_retrieved_sources():
    """The finding: a fabricated hostname that no placeholder rule can catch."""
    record_retrieved_url(REAL)
    text = f"Rankings [Onyx]({REAL}) and data needs [Data Quality Report]({FAKE})."
    assert extract_citations(text, take_seen_sources()) == [
        {"source": "Onyx", "page": REAL, "verified": True},
        {"source": "Data Quality Report", "page": FAKE, "verified": False},
    ]


def test_verification_ignores_cosmetic_url_differences():
    """The agent rewrites URLs as it copies them; a www or utm difference is the
    same source and must not read as fabricated."""
    record_retrieved_url("https://onyx.app/leaderboard")
    text = "See [Onyx](https://www.onyx.app/leaderboard/?utm_source=chat)."
    assert extract_citations(text, take_seen_sources())[0]["verified"] is True


def test_invented_path_on_a_real_domain_is_unverified():
    """Nothing currently catches this: the host resolves, the page doesn't."""
    record_retrieved_url("https://onyx.app/leaderboard")
    text = "See [Onyx](https://onyx.app/pages/that-were-never-fetched)."
    assert extract_citations(text, take_seen_sources())[0]["verified"] is False


def test_unverified_citations_are_kept_not_dropped():
    """The ledger cannot be complete — a link quoted inside a scraped page is a
    real source the run never fetched itself. Dropping on a miss would delete
    genuine citations, so the finding is labelled and left in place."""
    result = extract_citations(f"[Somewhere]({FAKE})", [])
    assert result == [{"source": "Somewhere", "page": FAKE, "verified": False}]


def test_no_verified_claim_without_a_ledger():
    """Callers that pass nothing get the old behaviour: no field, no claim."""
    assert extract_citations(f"[Onyx]({REAL})") == [{"source": "Onyx", "page": REAL}]


def test_rag_document_citations_carry_no_verified_field():
    """There is no URL to check a PDF page against, so claiming either way
    would be a lie."""
    result = extract_citations("SOURCE: report.pdf (Page: 3)\n---\nbody", ["onyx.app/x"])
    assert result == [{"source": "report.pdf", "page": "3"}]


def test_placeholder_urls_are_still_dropped_before_verification():
    """Reserved names can't be real, so they don't get a `verified: false` —
    they leave entirely."""
    record_retrieved_url(REAL)
    text = f"[Onyx]({REAL}) and [studies](https://www.example.com/research-study)"
    assert extract_citations(text, take_seen_sources()) == [
        {"source": "Onyx", "page": REAL, "verified": True},
    ]


def test_search_tool_ledgers_the_results_it_shows(monkeypatch):
    """The end-to-end contract: what the agent is shown is what counts as seen."""
    from tools.search import SearxngSearchTool

    tool = SearxngSearchTool()
    monkeypatch.setattr(tool, "_execute_search", lambda query: {"results": [
        {"title": "Onyx", "url": REAL, "content": "..."},
    ]})
    tool._run("open weight llm leaderboard")

    text = f"[Onyx]({REAL}) beats [Fake]({FAKE})."
    assert [c["verified"] for c in extract_citations(text, take_seen_sources())] == [True, False]
