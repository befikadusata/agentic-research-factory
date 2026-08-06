"""Content-addressed cache for embedding vectors, in Redis.

Embedding the same text with the same model always yields the same vector, so
every repeat is pure waste — a paid HTTP round trip on the Gemini path, CPU on
the local one. Repeats are not rare here:

- A ReAct agent loops. `search_documents` fires several times per node with
  overlapping phrasings, and a review FAIL re-runs the whole research segment
  with the same topic.
- Sub-query expansion is generated at temperature 0.4, which produces
  near-duplicate strings across attempts and often the original query verbatim
  as a fallback.
- Re-ingesting a corrected or re-uploaded document re-embeds every chunk that
  did not change, which for a small edit is nearly all of them.

Separate from `utils/cache.py`'s `ToolCache`, which stores JSON tool output on a
7-day TTL. Vectors are hot, fixed-width, and numerous enough that JSON's ~8KB
per 384-dim vector against 1.5KB packed is worth its own store.

## Keying

The key covers *provider, model, and dimension*, not just the text. Vectors from
two different models are not comparable, which is why `tools/rag.py` picks the
embedder from config alone. A cache keyed on text alone would still hit on the
old vectors the moment someone set or cleared `GEMINI_API_KEY`; keyed this way,
flipping providers simply misses every entry.

## Failure

Never raises. A cache miss and a broken Redis are the same thing to the caller:
compute it. Nothing here is allowed to break embedding.
"""

import hashlib
import struct

import redis

from config import settings
from logger import logger

_KEY_PREFIX = "emb:"


class EmbeddingCache:
    def __init__(self, ttl_days: int = 30):
        # Vectors for a fixed (model, text) never change, so the TTL is eviction
        # policy rather than freshness — long enough that a re-ingest days later
        # still hits, short enough that a retired model's entries age out.
        self.ttl = ttl_days * 24 * 60 * 60
        self.client = None
        if not settings.EMBEDDING_CACHE_ENABLED:
            return
        try:
            # No decode_responses: values are packed floats, not text. The
            # ToolCache client decodes, which is why this cannot share it.
            self.client = redis.from_url(settings.REDIS_URL)
            self.client.ping()
        except Exception as e:
            logger.warning("embedding_cache_unavailable", error=str(e))
            self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _key(self, model_id: str, text: str) -> str:
        digest = hashlib.sha256(f"{model_id}\x00{text}".encode()).hexdigest()
        return f"{_KEY_PREFIX}{digest}"

    def get_many(self, model_id: str, texts: list[str]) -> list[list[float] | None]:
        """Positional lookup: result[i] is the vector for texts[i], or None."""
        if not self.enabled or not texts:
            return [None] * len(texts)

        try:
            blobs = self.client.mget([self._key(model_id, text) for text in texts])
        except Exception as e:
            logger.warning("embedding_cache_read_failed", error=str(e))
            return [None] * len(texts)

        return [self._unpack(blob) for blob in blobs]

    def set_many(self, model_id: str, pairs: list[tuple[str, list[float]]]) -> None:
        if not self.enabled or not pairs:
            return
        try:
            pipe = self.client.pipeline()
            for text, vector in pairs:
                pipe.setex(self._key(model_id, text), self.ttl, self._pack(vector))
            pipe.execute()
        except Exception as e:
            logger.warning("embedding_cache_write_failed", error=str(e))

    @staticmethod
    def _pack(vector: list[float]) -> bytes:
        # Explicit little-endian float32. Native byte order would corrupt entries
        # for anyone sharing a Redis across architectures, and a byte-swapped
        # vector reads as valid: right length, plausible magnitudes, wrong
        # retrieval. float32 costs nothing — pgvector's element type is single
        # precision.
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _unpack(blob: bytes | None) -> list[float] | None:
        if not blob:
            return None
        if len(blob) % 4:
            # Truncated or foreign value. Treat as a miss rather than raising:
            # the caller recomputes and overwrites it.
            logger.warning("embedding_cache_corrupt_entry", size=len(blob))
            return None
        return list(struct.unpack(f"<{len(blob) // 4}f", blob))


embedding_cache = EmbeddingCache()
