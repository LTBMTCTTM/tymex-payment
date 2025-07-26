"""Utility functions for idempotency key handling with Redis."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import logging

import redis.asyncio as redis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_TTL: int = int(os.getenv("IDEM_TTL_SEC", "86400"))

logger = logging.getLogger(__name__)


class IdemRedisClient:
    """Context-managed Redis client for idempotency key handling."""
    def __init__(self, redis_url: str = None, ttl: int = None):
        self._redis_url = redis_url or _REDIS_URL
        self._ttl = ttl or _TTL
        self.client: Optional[redis.Redis] = None

    async def __aenter__(self):
        self.client = redis.from_url(self._redis_url, decode_responses=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _key(self, idem_key: str) -> str:
        return f"idem:{idem_key}"

    async def save_response(self, idem_key: str, request_hash: str, response_json: Dict[str, Any]) -> None:
        payload = json.dumps({"hash": request_hash, "response": response_json})
        await self.client.set(await self._key(idem_key), payload, ex=self._ttl)

    async def get_saved_response(self, idem_key: str) -> Optional[Dict[str, Any]]:
        raw = await self.client.get(await self._key(idem_key))
        if raw is None or raw == "LOCK":
            return None
        try:
            data = json.loads(raw)
            return data.get("response")
        except json.JSONDecodeError:
            return None

    async def acquire_lock(self, idem_key: str) -> bool:
        return await self.client.setnx(await self._key(idem_key), "LOCK")

    async def release_lock(self, idem_key: str) -> None:
        raw = await self.client.get(await self._key(idem_key))
        if raw == "LOCK":
            await self.client.delete(await self._key(idem_key))
