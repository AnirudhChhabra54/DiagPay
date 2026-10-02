import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings
from app.logging_config import logger

settings = get_settings()


class CacheService:
    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._is_connected = False

    async def get_client(self) -> aioredis.Redis | None:
        if not settings.REDIS_ENABLED:
            return None
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                )
                await self._redis.ping()
                self._is_connected = True
                logger.info("redis_connected", url=settings.REDIS_URL)
            except Exception as e:
                self._is_connected = False
                self._redis = None
                logger.warning("redis_connection_failed", error=str(e))
        return self._redis

    async def get(self, key: str) -> Any | None:
        """Fetch cached data from Redis. Returns None if key doesn't exist or on failure."""
        try:
            client = await self.get_client()
            if not client:
                return None
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("cache_read_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Store serializable data into Redis cache with TTL."""
        try:
            client = await self.get_client()
            if not client:
                return False
            ttl = ttl or settings.CACHE_TTL_SECONDS
            await client.set(key, json.dumps(value, default=str), ex=ttl)
            return True
        except Exception as e:
            logger.warning("cache_write_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a single key from Redis."""
        try:
            client = await self.get_client()
            if not client:
                return False
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def invalidate_patterns(self, *patterns: str) -> None:
        """Invalidate keys matching specified pattern(s). Gracefully degrades."""
        try:
            client = await self.get_client()
            if not client:
                return
            for pattern in patterns:
                async for key in client.scan_iter(match=pattern):
                    await client.delete(key)
            logger.info("cache_invalidated", patterns=patterns)
        except Exception as e:
            logger.warning("cache_invalidation_error", patterns=patterns, error=str(e))

    async def ping(self) -> bool:
        """Check if Redis connection is alive."""
        if not settings.REDIS_ENABLED:
            return False
        try:
            client = await self.get_client()
            if client:
                await client.ping()
                return True
            return False
        except Exception:
            return False

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._is_connected = False


cache_service = CacheService()
