from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.centre import DiagnosticCentre
    from app.models.test import DiagnosticTest


class CentreTest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "centre_tests"

    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    centre: Mapped[DiagnosticCentre] = relationship(
        "DiagnosticCentre",
        back_populates="centre_tests",
    )
    test: Mapped[DiagnosticTest] = relationship(
        "DiagnosticTest",
        back_populates="centre_tests",
    )

    __table_args__ = (UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),)
