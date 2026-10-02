from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.centre import DiagnosticCentre
    from app.models.payment import Payment
    from app.models.test import DiagnosticTest
    from app.models.user import User


class BookingStatus(enum.StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Booking(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_centres.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_tests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appointment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, native_enum=False, length=20),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="bookings",
    )
    centre: Mapped[DiagnosticCentre] = relationship(
        "DiagnosticCentre",
        back_populates="bookings",
    )
    test: Mapped[DiagnosticTest] = relationship(
        "DiagnosticTest",
        back_populates="bookings",
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment",
        back_populates="booking",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_bookings_active_user_slot",
            "user_id",
            "test_id",
            "centre_id",
            "appointment_at",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'CONFIRMED')"),
            sqlite_where=text("status IN ('PENDING', 'CONFIRMED')"),
        ),
    )
