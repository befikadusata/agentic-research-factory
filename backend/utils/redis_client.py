import redis.asyncio as redis
from config import settings

# Create a connection pool for efficient Redis access
redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis_client():
    return redis.Redis(connection_pool=redis_pool)
