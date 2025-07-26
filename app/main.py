import hashlib
import json
import asyncio
from typing import Callable
from uuid import uuid4
import logging
from logging.config import dictConfig

from fastapi import FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse

from .idem import IdemRedisClient
from .models import PaymentRequest, PaymentResponse, PaymentStatus

import os
from dotenv import load_dotenv

load_dotenv()
LOCK_TIMEOUT = float(os.getenv("LOCK_TIMEOUT", "5"))  # seconds

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s | %(filename)s:%(lineno)d | %(levelname)s | %(message)s",
            "use_colors": None,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "WARNING"},
    },
}

# Apply the logging configuration as early as possible so that all subsequent
# imports pick up the settings.
dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)


app = FastAPI(title="Payment API with Idempotency")


async def idempotency_middleware(request: Request, call_next: Callable):
    idem_key = request.headers.get("Idempotency-Key")
    if not idem_key:
        # No idempotency header: proceed normally
        return await call_next(request)

    async with IdemRedisClient() as idem:
        # Check if response already stored
        saved = await idem.get_saved_response(idem_key)
        if saved is not None:
            # Return cached result
            return JSONResponse(content=saved)

        # Attempt to acquire lock; if false, someone else is processing
        got_lock = await idem.acquire_lock(idem_key)
        if not got_lock:
            # Wait for the first request to finish and save the result (idempotency)
            elapsed = 0.0
            interval = 0.05  # 50ms
            while elapsed < LOCK_TIMEOUT:
                saved = await idem.get_saved_response(idem_key)
                if saved is not None:
                    return JSONResponse(content=saved)
                await asyncio.sleep(interval)
                elapsed += interval
            return Response(status_code=500, content="Timeout waiting for idempotent result")

        # Compute request hash
        body_bytes = await request.body()
        body_hash = hashlib.sha256(body_bytes).hexdigest()

        # Need to create a new request object with body reset
        async def receive() -> dict:  # type: ignore[override]
            return {"type": "http.request", "body": body_bytes}

        request = Request(request.scope, receive)  # type: ignore[arg-type]

        try:
            response: Response = await call_next(request)
            if response.status_code < 400:
                # Save successful response for future calls
                try:
                    # Collect the response body **once** while keeping it available for the client
                    collected = b"".join([chunk async for chunk in response.body_iterator])

                    # Re-attach the iterator so the body can still be streamed to the client
                    async def new_body_iterator():
                        yield collected

                    response.body_iterator = new_body_iterator()
                    # Ensure the Content-Length header matches the actual body size
                    response.headers["content-length"] = str(len(collected))
                    await idem.save_response(idem_key, body_hash, json.loads(collected.decode()))
                except Exception as e:  # pragma: no cover
                    logger.exception("Failed to save response: %s", e)
            return response
        finally:
            # Release lock if we never stored value (e.g., exception)
            await idem.release_lock(idem_key)


app.middleware("http")(idempotency_middleware)


@app.post("/payments", response_model=PaymentResponse)
async def create_payment(payload: PaymentRequest, idem_key: str | None = Header(None, alias="Idempotency-Key")):
    """Simulate a payment charge. Real integration would contact payment gateway."""
    # Fake processing logic
    payment_id = uuid4()

    response = PaymentResponse(
        id=payment_id,
        amount=payload.amount,
        currency=payload.currency,
        status=PaymentStatus.succeeded,
    )
    return response
