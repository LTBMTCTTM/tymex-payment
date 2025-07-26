import asyncio
import logging
import pytest
from app.main import app
from app.idem import IdemRedisClient
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

logger = logging.getLogger(__name__)

client = TestClient(app)

@pytest.fixture(autouse=True)
async def cleanup_redis():
    # Cleanup all test keys after each test
    async with IdemRedisClient() as idem:
        await idem.client.flushdb()
    yield
    # flush again after
    async with IdemRedisClient() as idem:
        await idem.client.flushdb()

@pytest.mark.asyncio
async def test_idempotency_same_key():
    body = {"amount": 20.0, "currency": "USD"}
    headers = {"Idempotency-Key": "abc123"}

    async with IdemRedisClient() as idem:
        # clear old key to make sure test is clean
        await idem.client.delete(await idem._key("abc123"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.post("/payments", json=body, headers=headers)
        r2 = await ac.post("/payments", json=body, headers=headers)
    
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_concurrent_requests_same_key():
    """
    Test that concurrent requests with the same idempotency key:
    - Only one is processed (side effect happens once)
    - All responses are consistent (either both 200 with same body, or one 200 and one 409/conflict, but both reference the same result)
    """
    body = {"amount": 30.0, "currency": "USD"}
    headers = {"Idempotency-Key": "concurrent"}

    # Ensure the idempotency key is clean before starting
    async with IdemRedisClient() as idem:
        await idem.client.delete(await idem._key("concurrent"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async def do_request():
            return await ac.post("/payments", json=body, headers=headers)
        # Fire off two concurrent requests with the same idempotency key
        responses = await asyncio.gather(*[do_request() for _ in range(10)])

    bodies = [r.json() for r in responses]
    codes = [r.status_code for r in responses]

    # debug
    logger.debug(f"Responses: {bodies}")
    logger.debug(f"Codes: {codes}")

    # Check that all responses are consistent
    assert len(set(map(lambda b: b["id"], bodies))) == 1, "Multiple payments created!"
    assert all(code == 200 for code in codes), f"Not all responses are 200: {codes}"