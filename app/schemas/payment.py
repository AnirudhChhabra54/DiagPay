import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


class PaymentSimulateRequest(BaseModel):
    booking_id: uuid.UUID = Field(..., description="ID of the booking to pay for")
    simulate_result: PaymentStatus = Field(
        default=PaymentStatus.SUCCESS,
        description="Simulated payment outcome: SUCCESS or FAILED",
    )


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    provider_payment_id: str
    event_id: str
    amount: Decimal
    status: PaymentStatus
    booking_status: BookingStatus
    created_at: datetime
    updated_at: datetime


class WebhookPayload(BaseModel):
    event_id: str = Field(..., min_length=1, description="Unique event ID for idempotency")
    provider_payment_id: str = Field(
        ..., min_length=1, description="Unique payment reference from provider"
    )
    booking_id: uuid.UUID = Field(..., description="Target booking UUID")
    status: PaymentStatus = Field(..., description="Payment outcome: SUCCESS or FAILED")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Charged amount")


class WebhookResponse(BaseModel):
    status: str
    message: str
    idempotent: bool
    payment_id: uuid.UUID | None = None
    booking_id: uuid.UUID
    booking_status: BookingStatus
