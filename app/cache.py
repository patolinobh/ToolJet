import os
import json
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))


class Cache:
    def __init__(self):
        self._client = None

    async def _ensure(self):
        if not self._client:
            self._client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

    async def get(self, key: str):
        await self._ensure()
        v = await self._client.get(key)
        if not v:
            return None
        try:
            return json.loads(v)
        except Exception:
            return None

    async def set(self, key: str, value, ttl: int = CACHE_TTL):
        await self._ensure()
        await self._client.set(key, json.dumps(value), ex=ttl)
