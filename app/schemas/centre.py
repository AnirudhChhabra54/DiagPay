import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CentreBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    location: str = Field(..., min_length=2, max_length=500)
    is_active: bool = True


class CentreCreate(CentreBase):
    pass


class CentreUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    location: str | None = Field(None, min_length=2, max_length=500)
    is_active: bool | None = None


class CentreResponse(CentreBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
