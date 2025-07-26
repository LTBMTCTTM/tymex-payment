"""Utility functions for idempotency key handling with Redis."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis
from fastapi import HTTPException

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_TTL: int = int(os.getenv("IDEM_TTL_SEC", "86400"))


async def get_redis() -> "redis.Redis":
    """Return a singleton Redis client (async)."""
    return redis.from_url(_REDIS_URL, decode_responses=True)


async def _key(idem_key: str) -> str:
    return f"idem:{idem_key}"


async def save_response(idem_key: str, request_hash: str, response_json: Dict[str, Any]) -> None:
    """Persist the request hash & response under the idempotency key.

    We store both hash & response so that if clients send a different request body with the
    same key we can detect misuse.
    """
    client = await get_redis()
    payload = json.dumps({"hash": request_hash, "response": response_json})
    await client.set(await _key(idem_key), payload, ex=_TTL)


async def get_saved_response(idem_key: str) -> Optional[Dict[str, Any]]:
    client = await get_redis()
    raw = await client.get(await _key(idem_key))
    if raw is None or raw == "LOCK":
        return None
    try:
        data = json.loads(raw)
        return data.get("response")
    except json.JSONDecodeError:
        return None


async def acquire_lock(idem_key: str) -> bool:
    """Attempt to set a lock for this idempotency key.

    Returns True if we successfully acquired the lock (i.e. we are the first request),
    False if another process already holds it.
    """
    client = await get_redis()
    return await client.setnx(await _key(idem_key), "LOCK")


async def release_lock(idem_key: str) -> None:
    client = await get_redis()
    # If still "LOCK" (we crashed before saving), delete so future calls can proceed.
    raw = await client.get(await _key(idem_key))
    if raw == "LOCK":
        await client.delete(await _key(idem_key))
