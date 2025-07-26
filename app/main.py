from __future__ import annotations

import hashlib
import json
from typing import Callable
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse

from .idem import acquire_lock, get_saved_response, release_lock, save_response
from .models import PaymentRequest, PaymentResponse, PaymentStatus

app = FastAPI(title="Payment API with Idempotency")


async def idempotency_middleware(request: Request, call_next: Callable):
    idem_key = request.headers.get("Idempotency-Key")
    print(idem_key)
    if not idem_key:
        # No idempotency header: proceed normally
        return await call_next(request)

    # Check if response already stored
    saved = await get_saved_response(idem_key)
    if saved is not None:
        # Return cached result
        return JSONResponse(content=saved)

    # Attempt to acquire lock; if false, someone else is processing
    got_lock = await acquire_lock(idem_key)
    if not got_lock:
        # Another request in-flight; return 409
        return Response(status_code=status.HTTP_409_CONFLICT, content="Request is being processed")

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
                if isinstance(response, JSONResponse):
                    data = response.body
                else:
                    data = await response.body()
                await save_response(idem_key, body_hash, json.loads(data))
            except Exception:  # pragma: no cover
                pass
        return response
    finally:
        # Release lock if we never stored value (e.g., exception)
        await release_lock(idem_key)


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
