"""Pydantic models used by the payment API."""
from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, PositiveFloat


class PaymentStatus(str, Enum):
    succeeded = "succeeded"
    failed = "failed"


class PaymentRequest(BaseModel):
    amount: PositiveFloat = Field(..., json_schema_extra={"example": 100.0})
    currency: str = Field("USD", min_length=3, max_length=3, json_schema_extra={"example": "USD"})


class PaymentResponse(BaseModel):
    id: UUID
    amount: float
    currency: str
    status: PaymentStatus
