import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_idempotency_same_key():
    body = {"amount": 20.0, "currency": "USD"}
    headers = {"Idempotency-Key": "abc123"}

    r1 = client.post("/payments", json=body, headers=headers)
    r2 = client.post("/payments", json=body, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


def test_concurrent_requests_same_key():
    body = {"amount": 30.0, "currency": "USD"}
    headers = {"Idempotency-Key": "concurrent"}

    async def do_request():
        return client.post("/payments", json=body, headers=headers)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    responses = loop.run_until_complete(asyncio.gather(*[loop.run_in_executor(None, do_request) for _ in range(2)]))

    statuses = {resp.status_code for resp in responses}
    assert statuses <= {200, 409}
