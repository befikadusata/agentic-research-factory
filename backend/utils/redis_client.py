import asyncio
import redis.asyncio as redis
from config import settings

LOG_CHANNEL_PREFIX   = "run_log:"
HITL_SIGNAL_KEY      = "run_hitl_signal:"
HITL_INSTRUCTION_KEY = "run_hitl_instr:"

_redis_client: redis.Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


def init_redis_pool() -> redis.Redis:
    global _redis_client, _redis_loop
    _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        _redis_loop = asyncio.get_running_loop()
    except RuntimeError:
        _redis_loop = None
    return _redis_client


async def close_redis_pool() -> None:
    global _redis_client, _redis_loop
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        _redis_loop = None


async def get_redis_client() -> redis.Redis:
    global _redis_client, _redis_loop
    current_loop = asyncio.get_running_loop()
    # Recreate if not yet initialised or if the event loop has changed (e.g. between tests)
    if _redis_client is None or current_loop is not _redis_loop:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis_loop = current_loop
    return _redis_client
