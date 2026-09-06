import json
import logging
from typing import Optional, Any
from app.config import settings

logger = logging.getLogger("lively.db.redis")

class RedisClient:
    """
    Async Redis client with graceful in-memory fallback for development and test resilience.
    """
    def __init__(self):
        self._redis = None
        self._memory_cache: dict[str, str] = {}
        self.url = settings.REDIS_URL

    async def connect(self):
        if self.url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self.url, decode_responses=True)
                await self._redis.ping()
                logger.info("Connected to Redis instance.")
            except Exception as e:
                logger.warning(f"Redis connection unavailable ({e}). Using in-memory store.")
                self._redis = None

    async def get(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return await self._redis.get(key)
            except Exception:
                pass
        return self._memory_cache.get(key)

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        if self._redis:
            try:
                if expire:
                    await self._redis.setex(key, expire, value)
                else:
                    await self._redis.set(key, value)
                return True
            except Exception:
                pass
        self._memory_cache[key] = value
        return True

    async def delete(self, key: str) -> bool:
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        self._memory_cache.pop(key, None)
        return True

redis_client = RedisClient()
