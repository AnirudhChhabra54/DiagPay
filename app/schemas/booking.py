import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.booking import BookingStatus
from app.schemas.centre import CentreResponse
from app.schemas.test import TestResponse


class BookingCreate(BaseModel):
    centre_id: uuid.UUID
    test_id: uuid.UUID
    appointment_at: datetime = Field(
        ..., description="Target appointment datetime in UTC (must be in future)"
    )

    @field_validator("appointment_at")
    @classmethod
    def validate_future_time(cls, v: datetime) -> datetime:
        # Normalize to UTC or check against now
        now = datetime.now(UTC)
        target = v if v.tzinfo else v.replace(tzinfo=UTC)
        if target <= now:
            raise ValueError("Appointment must be scheduled for a future time")
        return target


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    appointment_at: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime

    centre: CentreResponse | None = None
    test: TestResponse | None = None


class BookingCancelResponse(BaseModel):
    id: uuid.UUID
    status: BookingStatus
    message: str
