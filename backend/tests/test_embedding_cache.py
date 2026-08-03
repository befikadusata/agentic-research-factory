"""Tests for the Redis embedding cache.

The cache is disabled under pytest (config.py sets EMBEDDING_CACHE_ENABLED=False
when TESTING=1), because a store shared across tests would make "did this call
the embedder?" assertions depend on what an earlier test happened to warm. These
tests construct their own instance with the flag forced on, so the cache is
exercised deliberately and nothing else in the suite is touched by it.

They need the Redis that `docker compose up -d redis` provides — the same one
the rest of the suite already uses.
"""
import struct
import uuid
from unittest.mock import MagicMock, patch

import pytest

from config import settings
from utils.embedding_cache import EmbeddingCache

VECTOR = [0.1, -0.25, 3.5, 0.0]


@pytest.fixture
def cache():
    with patch.object(settings, "EMBEDDING_CACHE_ENABLED", True):
        instance = EmbeddingCache(ttl_days=1)
    if not instance.enabled:
        pytest.skip("redis unavailable")
    return instance


@pytest.fixture
def model():
    """A vector-space identity unique to this test.

    Deliberately not a fixed constant with a flushdb teardown: REDIS_URL is not
    redirected under TESTING the way DATABASE_URL is, so this is the developer's
    real Redis — the Celery broker, HITL signals, and tool cache all live in it,
    and flushing would take them out. Keys are namespaced by model id, so a
    unique one per test cannot collide with anything real or with another test,
    and the TTL clears it without a teardown that could reach further than
    intended.
    """
    return f"test:{uuid.uuid4()}:384"


# ── round trip ───────────────────────────────────────────────────────────────

def test_stores_and_returns_a_vector(cache, model):
    cache.set_many(model, [("hello", VECTOR)])
    assert cache.get_many(model, ["hello"]) == [pytest.approx(VECTOR)]


def test_miss_returns_none_positionally(cache, model):
    """Callers index the result against their input list, so a miss has to hold
    its slot rather than shorten the list."""
    cache.set_many(model, [("b", VECTOR)])
    result = cache.get_many(model, ["a", "b", "c"])

    assert result[0] is None
    assert result[1] == pytest.approx(VECTOR)
    assert result[2] is None


def test_empty_input_returns_empty(cache, model):
    assert cache.get_many(model, []) == []


# ── keying ───────────────────────────────────────────────────────────────────

def test_a_different_model_is_a_different_key(cache, model):
    """The bug this prevents: flipping GEMINI_API_KEY would otherwise serve
    Gemini vectors to the local model and mix two vector spaces in one
    collection — silently, since both are 384-dimensional."""
    cache.set_many(f"gemini:{model}", [("hello", VECTOR)])
    assert cache.get_many(f"local:{model}", ["hello"]) == [None]


def test_a_different_dimension_is_a_different_key(cache, model):
    cache.set_many(f"{model}:384", [("hello", VECTOR)])
    assert cache.get_many(f"{model}:768", ["hello"]) == [None]


def test_text_and_model_cannot_collide_across_the_separator(cache):
    """Keys join model and text; without a separator "a" + "bc" and "ab" + "c"
    would hash identically."""
    assert cache._key("a", "bc") != cache._key("ab", "c")


# ── packing ──────────────────────────────────────────────────────────────────

def test_packing_is_little_endian_float32(cache):
    """Pinned explicitly: native byte order would corrupt entries across
    architectures sharing a Redis, and a byte-swapped vector has the right
    length and plausible magnitudes, so retrieval would degrade silently rather
    than fail."""
    assert EmbeddingCache._pack([1.0, 2.0]) == struct.pack("<2f", 1.0, 2.0)


def test_full_dimension_vector_round_trips(cache, model):
    vector = [i / 1000 for i in range(384)]
    cache.set_many(model, [("big", vector)])
    assert cache.get_many(model, ["big"])[0] == pytest.approx(vector, abs=1e-6)


def test_corrupt_entry_reads_as_a_miss(cache, model):
    """A truncated value must not raise — the caller recomputes and overwrites."""
    cache.client.set(cache._key(model, "bad"), b"\x00\x01\x02")
    assert cache.get_many(model, ["bad"]) == [None]


# ── failure is never fatal ───────────────────────────────────────────────────

def test_disabled_cache_is_a_silent_miss():
    with patch.object(settings, "EMBEDDING_CACHE_ENABLED", False):
        instance = EmbeddingCache()

    assert not instance.enabled
    assert instance.get_many("test:disabled:384", ["a", "b"]) == [None, None]
    instance.set_many("test:disabled:384", [("a", VECTOR)])  # must not raise


def test_read_failure_degrades_to_a_miss(cache, model):
    """A cache that can fail the operation it accelerates is worse than none."""
    with patch.object(cache.client, "mget", side_effect=RuntimeError("redis gone")):
        assert cache.get_many(model, ["a"]) == [None]


def test_write_failure_is_swallowed(cache, model):
    with patch.object(cache.client, "pipeline", side_effect=RuntimeError("redis gone")):
        cache.set_many(model, [("a", VECTOR)])  # must not raise


def test_unreachable_redis_disables_rather_than_raising():
    with patch.object(settings, "EMBEDDING_CACHE_ENABLED", True), \
         patch("utils.embedding_cache.redis.from_url", side_effect=RuntimeError("no redis")):
        instance = EmbeddingCache()

    assert not instance.enabled


# ── integration with _embed ──────────────────────────────────────────────────

def test_embed_serves_repeats_from_cache_without_recomputing(cache, model):
    """The end the cache exists for: a second identical query costs nothing."""
    import tools.rag as rag

    embedder = MagicMock(return_value=[[0.5] * 4])
    with patch.object(rag.settings, "GEMINI_API_KEY", "test-key"), \
         patch("tools.rag.embedding_cache", cache), \
         patch("tools.rag._embedding_model_id", return_value=model), \
         patch("tools.rag._gemini_embed", embedder):
        first = rag._embed(["repeated query"])
        second = rag._embed(["repeated query"])

    assert embedder.call_count == 1
    assert first == second


def test_embed_computes_only_the_uncached_texts(cache, model):
    import tools.rag as rag

    cache.set_many(model, [("warm", [0.9] * 4)])

    with patch.object(rag.settings, "GEMINI_API_KEY", "test-key"), \
         patch("tools.rag.embedding_cache", cache), \
         patch("tools.rag._embedding_model_id", return_value=model), \
         patch("tools.rag._gemini_embed", return_value=[[0.1] * 4]) as embedder:
        result = rag._embed(["warm", "cold"])

    assert embedder.call_args[0][0] == ["cold"]
    assert result[0] == pytest.approx([0.9] * 4)
    assert result[1] == pytest.approx([0.1] * 4)
