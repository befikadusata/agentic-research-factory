import json
import hashlib
import redis
from datetime import timedelta
from typing import Any, Optional
from logger import logger
from config import settings

class ToolCache:
    def __init__(self, ttl_days: int = 7):
        self.ttl = int(timedelta(days=ttl_days).total_seconds())
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.client.ping()
        except Exception as e:
            logger.error("redis_connection_failed", url=settings.REDIS_URL, error=str(e))
            self.client = None

    def _get_cache_key(self, tool_name: str, key: str) -> str:
        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return f"tool_cache:{tool_name}:{hashed_key}"

    def get(self, tool_name: str, key: str) -> Optional[Any]:
        if not self.client:
            return None
            
        redis_key = self._get_cache_key(tool_name, key)
        try:
            data = self.client.get(redis_key)
            if not data:
                return None
            
            cached_data = json.loads(data)
            return cached_data.get("result")
        except Exception as e:
            logger.warning("cache_read_failed", tool=tool_name, error=str(e))
            return None

    def set(self, tool_name: str, key: str, result: Any):
        if not self.client:
            return
            
        redis_key = self._get_cache_key(tool_name, key)
        try:
            data = {
                "result": result
            }
            self.client.setex(
                name=redis_key,
                time=self.ttl,
                value=json.dumps(data)
            )
        except Exception as e:
            logger.warning("cache_write_failed", tool=tool_name, error=str(e))

tool_cache = ToolCache()
