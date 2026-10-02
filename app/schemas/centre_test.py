import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.test import TestResponse


class CentreTestCreate(BaseModel):
    test_id: uuid.UUID
    price: Decimal = Field(
        ..., gt=0, decimal_places=2, description="Price of the test at this centre"
    )
    is_available: bool = Field(True, description="Availability flag")


class CentreTestUpdate(BaseModel):
    price: Decimal | None = Field(None, gt=0, decimal_places=2)
    is_available: bool | None = None


class CentreTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    price: Decimal
    is_available: bool
    created_at: datetime
    updated_at: datetime
    test: TestResponse | None = None


class CentreTestDetailResponse(BaseModel):
    """View of a test offered by a specific diagnostic centre."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID  # centre_test id
    test_id: uuid.UUID
    test_name: str
    description: str | None
    price: Decimal
    is_available: bool
