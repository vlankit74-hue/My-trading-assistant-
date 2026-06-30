"""
Thin Redis cache wrapper. Premium keys still have rate limits — this layer
de-duplicates repeated requests across connected dashboard clients and
gives the scheduler a place to publish fresh data for WebSocket fan-out.
"""
import json

import redis.asyncio as redis
import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_SEC = 30


class CacheService:
    def __init__(self, settings: Settings):
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def get_json(self, key: str) -> dict | list | None:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict | list, ttl: int = _DEFAULT_TTL_SEC) -> None:
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def publish(self, channel: str, message: dict) -> None:
        await self._redis.publish(channel, json.dumps(message, default=str))

    def pubsub(self):
        return self._redis.pubsub()

    async def close(self) -> None:
        await self._redis.close()
