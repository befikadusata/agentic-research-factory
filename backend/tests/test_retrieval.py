"""Tests for Sprint 4 retrieval hardening: query_rewriter fallback + citation extraction."""
import pytest
from unittest.mock import MagicMock, patch


# ── query_rewriter ────────────────────────────────────────────────────────────

def test_rewrite_query_success():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '"expanded search query"'
    with patch("services.query_rewriter.completion", return_value=mock_response), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import rewrite_query
        result = rewrite_query("original query")
    assert result == "expanded search query"


def test_rewrite_query_strips_quotes():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "'quoted result'"
    with patch("services.query_rewriter.completion", return_value=mock_response), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import rewrite_query
        result = rewrite_query("original")
    assert result == "quoted result"


def test_rewrite_query_fallback_on_exception():
    with patch("services.query_rewriter.completion", side_effect=Exception("API error")), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import rewrite_query
        result = rewrite_query("test topic")
    assert result == "test topic"


def test_rewrite_query_fallback_on_key_error():
    """Covers the case where get_completion_settings itself fails."""
    with patch("services.query_rewriter.get_completion_settings", side_effect=RuntimeError("missing key")):
        from services.query_rewriter import rewrite_query
        result = rewrite_query("fallback query")
    assert result == "fallback query"


# ── extract_citations ─────────────────────────────────────────────────────────

def test_extract_citations_parses_rag_output():
    from tools.rag import extract_citations
    text = (
        "SOURCE: report.pdf (Page: 3)\n---\nsome content\n\n"
        "================\n\n"
        "SOURCE: analysis.pdf (Page: 7)\n---\nother content"
    )
    result = extract_citations(text)
    assert result == [
        {"source": "report.pdf", "page": "3"},
        {"source": "analysis.pdf", "page": "7"},
    ]


def test_extract_citations_empty_on_no_sources():
    from tools.rag import extract_citations
    assert extract_citations("Plain text with no source markers.") == []


def test_extract_citations_deduplicates():
    from tools.rag import extract_citations
    text = (
        "SOURCE: doc.pdf (Page: 1)\n---\nchunk a\n\n"
        "SOURCE: doc.pdf (Page: 1)\n---\nchunk b"
    )
    result = extract_citations(text)
    assert result == [{"source": "doc.pdf", "page": "1"}]


def test_extract_citations_na_page():
    from tools.rag import extract_citations
    text = "SOURCE: unknown.pdf (Page: N/A)\n---\nsome text"
    result = extract_citations(text)
    assert result == [{"source": "unknown.pdf", "page": "N/A"}]


def test_extract_citations_parses_markdown_links():
    """§8.1 regression: every prompt (configs/prompts.yaml, agents/writer.py)
    instructs agents to cite sources as Markdown links, e.g. '[Title](URL)' —
    never the internal RAG 'SOURCE: ... (Page: ...)' format, which is only
    ever produced by RAGTool._run for internal-document search. Before this
    fix, extract_citations only knew the RAG format and returned [] for
    essentially every real web-search-driven run."""
    from tools.rag import extract_citations
    text = (
        "## Findings\n\n"
        "- Revenue grew 40% YoY [TechCrunch](https://techcrunch.com/article1).\n"
        "- Market share expanded [Company Blog](https://example.com/blog/post).\n"
    )
    result = extract_citations(text)
    assert result == [
        {"source": "TechCrunch", "page": "https://techcrunch.com/article1"},
        {"source": "Company Blog", "page": "https://example.com/blog/post"},
    ]


def test_extract_citations_deduplicates_markdown_links():
    from tools.rag import extract_citations
    text = (
        "First mention [Reuters](https://reuters.com/a) here.\n"
        "Second mention [Reuters](https://reuters.com/a) again."
    )
    result = extract_citations(text)
    assert result == [{"source": "Reuters", "page": "https://reuters.com/a"}]


def test_extract_citations_ignores_non_http_markdown_links():
    """In-page anchors and relative TOC links aren't source attributions."""
    from tools.rag import extract_citations
    text = "See [Section 2](#section-2) and [appendix](./appendix.md) for details."
    assert extract_citations(text) == []


def test_extract_citations_handles_mixed_rag_and_markdown_formats():
    from tools.rag import extract_citations
    text = (
        "SOURCE: internal_report.pdf (Page: 4)\n---\nsome internal content\n\n"
        "According to [Bloomberg](https://bloomberg.com/story) the market shifted."
    )
    result = extract_citations(text)
    assert result == [
        {"source": "internal_report.pdf", "page": "4"},
        {"source": "Bloomberg", "page": "https://bloomberg.com/story"},
    ]


# ── generate_sub_queries ──────────────────────────────────────────────────────

def test_generate_sub_queries_returns_list():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '["sub q1", "sub q2", "sub q3"]'
    with patch("services.query_rewriter.completion", return_value=mock_response), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import generate_sub_queries
        result = generate_sub_queries("complex research topic")
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0] == "sub q1"


def test_generate_sub_queries_fallback_on_bad_json():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "not valid json at all"
    with patch("services.query_rewriter.completion", return_value=mock_response), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import generate_sub_queries
        result = generate_sub_queries("fallback topic")
    assert result == ["fallback topic"]


def test_generate_sub_queries_fallback_on_exception():
    with patch("services.query_rewriter.completion", side_effect=RuntimeError("LLM down")), \
         patch("services.query_rewriter.get_completion_settings", return_value=MagicMock(model="m", api_key="k", base_url=None)):
        from services.query_rewriter import generate_sub_queries
        result = generate_sub_queries("original")
    assert result == ["original"]
