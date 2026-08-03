"""Tests for RAGTool vertical filter wiring."""
import pytest
from unittest.mock import MagicMock, patch


def _mock_vecs_setup(mock_collection):
    """Return a context-manager-compatible vecs client mock."""
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    return mock_client


@pytest.fixture
def mock_collection():
    col = MagicMock()
    col.query.return_value = []
    return col


def test_rag_no_vertical_filter(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag._keyword_search", return_value=[]), \
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        tool._run("query")

    _, kwargs = mock_collection.query.call_args
    assert kwargs.get("filters") is None


def test_rag_vertical_filter_applied(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test", vertical="lead_intel")

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag._keyword_search", return_value=[]) as keyword, \
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        tool._run("query")

    _, kwargs = mock_collection.query.call_args
    assert kwargs.get("filters") == {"vertical": {"$eq": "lead_intel"}}
    # The keyword half must honour the same vertical, or hybrid retrieval
    # leaks chunks the vector half is filtering out.
    assert keyword.call_args[0][-1] == "lead_intel"


def test_rag_returns_graceful_string_on_vecs_error():
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    with patch("tools.rag._get_client", side_effect=RuntimeError("vecs down")), \
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        result = tool._run("query")

    assert "unavailable" in result.lower()


def test_rag_fanout_calls_collection_once_per_subquery(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384] * 3), \
         patch("tools.rag._keyword_search", return_value=[]) as keyword, \
         patch("tools.rag.generate_sub_queries", return_value=["q1", "q2", "q3"]):
        tool._run("original query")

    assert mock_collection.query.call_count == 3
    assert keyword.call_count == 3


def test_rag_fanout_deduplicates_chunks(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    # Records are (id, metadata) 2-tuples — the shape vecs returns when
    # include_value=False.
    dup_chunk = ("abc-123", {"text": "shared chunk", "source": "doc.pdf", "page": "1"})
    unique_chunk = ("xyz-456", {"text": "unique chunk", "source": "doc.pdf", "page": "2"})
    mock_collection.query.side_effect = [
        [dup_chunk, unique_chunk],
        [dup_chunk],
    ]

    reranker_mock = MagicMock()
    reranker_mock.predict.return_value = [0.9, 0.5]

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384] * 2), \
         patch("tools.rag.generate_sub_queries", return_value=["q1", "q2"]), \
         patch("tools.rag._keyword_search", return_value=[]), \
         patch("tools.rag._reranker", return_value=reranker_mock):
        tool._run("original query")

    pairs_passed = reranker_mock.predict.call_args[0][0]
    assert len(pairs_passed) == 2
    # Dedup must survive into the rerank pool with real text attached.
    assert sorted(text for _, text in pairs_passed) == ["shared chunk", "unique chunk"]


def test_rag_merges_keyword_results_with_vector_results(mock_collection):
    """Chunks only the lexical half finds must reach the rerank pool."""
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    vector_hit = ("vec-1", {"text": "semantic chunk", "source": "a.pdf", "page": "1"})
    keyword_hit = ("kw-1", {"text": "ZX-9000 exact match", "source": "b.pdf", "page": "2"})
    mock_collection.query.return_value = [vector_hit]

    reranker_mock = MagicMock()
    reranker_mock.predict.return_value = [0.4, 0.9]

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag.generate_sub_queries", return_value=["q1"]), \
         patch("tools.rag._keyword_search", return_value=[keyword_hit]), \
         patch("tools.rag._reranker", return_value=reranker_mock):
        result = tool._run("ZX-9000")

    assert sorted(text for _, text in reranker_mock.predict.call_args[0][0]) == [
        "ZX-9000 exact match",
        "semantic chunk",
    ]
    # Reranker scored the keyword hit highest, so it must lead the output.
    assert result.index("ZX-9000 exact match") < result.index("semantic chunk")


# ── rerank threshold / abstention ─────────────────────────────────────────────

def _run_with_scores(mock_collection, hits, scores, threshold=0.0):
    """Drive RAGTool._run over a fixed candidate pool and reranker scores."""
    import tools.rag as rag

    mock_collection.query.return_value = list(hits)
    reranker_mock = MagicMock()
    reranker_mock.predict.return_value = list(scores)

    tool = rag.RAGTool(collection_name="ws_test")
    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag.generate_sub_queries", return_value=["q1"]), \
         patch("tools.rag._keyword_search", return_value=[]), \
         patch("tools.rag._reranker", return_value=reranker_mock), \
         patch.object(rag.settings, "RAG_MIN_RERANK_SCORE", threshold):
        return tool._run("query")


def test_rag_abstains_when_nothing_clears_threshold(mock_collection):
    """The pool is built recall-first, so a lexical match on an off-topic query
    nearly always returns *something*. Before the threshold the only way to get
    'nothing found' was an empty pool, so an unanswerable question got
    confidently-formatted irrelevant excerpts that the writer then cited."""
    hits = [
        ("a", {"text": "unrelated chunk", "source": "a.pdf", "page": 1}),
        ("b", {"text": "also unrelated", "source": "b.pdf", "page": 2}),
    ]
    result = _run_with_scores(mock_collection, hits, [-8.2, -5.1])
    assert result == "No relevant documents found."


def test_rag_keeps_only_chunks_above_threshold(mock_collection):
    hits = [
        ("a", {"text": "relevant chunk", "source": "a.pdf", "page": 3}),
        ("b", {"text": "borderline chunk", "source": "b.pdf", "page": 4}),
    ]
    result = _run_with_scores(mock_collection, hits, [4.5, -2.0])
    assert "relevant chunk" in result
    assert "borderline chunk" not in result


def test_rag_threshold_is_configurable(mock_collection):
    """A stricter floor drops a chunk that the default (0.0) would have kept."""
    hits = [("a", {"text": "weakly relevant", "source": "a.pdf", "page": 1})]
    assert "weakly relevant" in _run_with_scores(mock_collection, hits, [1.2])
    assert _run_with_scores(mock_collection, hits, [1.2], threshold=5.0) == (
        "No relevant documents found."
    )


# ── page-number rendering ─────────────────────────────────────────────────────

def test_rag_output_renders_real_page_numbers(mock_collection):
    hits = [("a", {"text": "chunk text", "source": "report.pdf", "page": 7})]
    assert "SOURCE: report.pdf (Page: 7)" in _run_with_scores(mock_collection, hits, [3.0])


def test_rag_output_falls_back_to_na_for_null_page(mock_collection):
    """Chunks ingested before page provenance existed carry the key with a null
    value, so `.get("page", "N/A")` never fired and citations read 'Page: None'."""
    hits = [("a", {"text": "chunk text", "source": "legacy.pdf", "page": None})]
    assert "SOURCE: legacy.pdf (Page: N/A)" in _run_with_scores(mock_collection, hits, [3.0])


def test_rag_rejects_unsafe_collection_name():
    """Collection names reach SQL as identifiers, so they must be validated."""
    from tools.rag import RAGTool
    tool = RAGTool(collection_name='ws"; DROP TABLE vecs.docs; --')

    with patch("tools.rag._get_client") as client, \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        result = tool._run("query")

    assert "unavailable" in result.lower()
    client.assert_not_called()


def test_embed_uses_gemini_when_key_configured():
    """With a Gemini key set, _embed must use Gemini and never the local model."""
    import tools.rag as rag

    with patch.object(rag.settings, "GEMINI_API_KEY", "test-key"), \
         patch("tools.rag._gemini_embed", return_value=[0.2] * 384) as gemini, \
         patch("tools.rag._embedder") as local:
        result = rag._embed(["a", "b"])

    assert gemini.call_count == 2
    local.assert_not_called()
    assert result == [[0.2] * 384, [0.2] * 384]


def test_embed_raises_instead_of_falling_back_to_local_model():
    """A Gemini failure must raise (not silently switch models and mix vectors)."""
    import tools.rag as rag

    with patch.object(rag.settings, "GEMINI_API_KEY", "test-key"), \
         patch("tools.rag._gemini_embed", side_effect=RuntimeError("gemini 429")), \
         patch("tools.rag._embedder") as local:
        with pytest.raises(RuntimeError):
            rag._embed(["a"])

    local.assert_not_called()


def test_embed_uses_local_model_when_no_gemini_key():
    """Without a Gemini key, _embed falls to the local sentence-transformers model."""
    import tools.rag as rag

    model = MagicMock()
    model.encode.return_value = _FakeArray([[0.3] * 384])
    with patch.object(rag.settings, "GEMINI_API_KEY", None), \
         patch("tools.rag._gemini_embed") as gemini, \
         patch("tools.rag._embedder", return_value=model):
        result = rag._embed(["a"])

    gemini.assert_not_called()
    assert result == [[0.3] * 384]


class _FakeArray:
    """Mimics the numpy array returned by SentenceTransformer.encode()."""
    def __init__(self, data):
        self._data = data

    def tolist(self):
        return self._data
