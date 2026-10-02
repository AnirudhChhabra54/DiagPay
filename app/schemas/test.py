import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_active: bool = True


class TestCreate(TestBase):
    pass


class TestUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


class TestResponse(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
