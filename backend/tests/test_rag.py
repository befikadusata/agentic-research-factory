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
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        tool._run("query")

    _, kwargs = mock_collection.query.call_args
    assert kwargs.get("query_filter") is None


def test_rag_vertical_filter_applied(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test", vertical="lead_intel")

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384]), \
         patch("tools.rag.generate_sub_queries", return_value=["query"]):
        tool._run("query")

    _, kwargs = mock_collection.query.call_args
    assert kwargs.get("query_filter") == {"vertical": {"$eq": "lead_intel"}}


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
         patch("tools.rag.generate_sub_queries", return_value=["q1", "q2", "q3"]):
        tool._run("original query")

    assert mock_collection.query.call_count == 3


def test_rag_fanout_deduplicates_chunks(mock_collection):
    from tools.rag import RAGTool
    tool = RAGTool(collection_name="ws_test")

    dup_chunk = ("abc-123", None, {"text": "shared chunk", "source": "doc.pdf", "page": "1"})
    unique_chunk = ("xyz-456", None, {"text": "unique chunk", "source": "doc.pdf", "page": "2"})
    mock_collection.query.side_effect = [
        [dup_chunk, unique_chunk],
        [dup_chunk],
    ]

    reranker_mock = MagicMock()
    reranker_mock.predict.return_value = [0.9, 0.5]

    with patch("tools.rag._get_client", return_value=_mock_vecs_setup(mock_collection)), \
         patch("tools.rag._embed", return_value=[[0.1] * 384] * 2), \
         patch("tools.rag.generate_sub_queries", return_value=["q1", "q2"]), \
         patch("tools.rag._reranker", return_value=reranker_mock):
        tool._run("original query")

    pairs_passed = reranker_mock.predict.call_args[0][0]
    assert len(pairs_passed) == 2
