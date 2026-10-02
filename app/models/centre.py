from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.centre_test import CentreTest


class DiagnosticCentre(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "diagnostic_centres"

    name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    centre_tests: Mapped[list[CentreTest]] = relationship(
        "CentreTest",
        back_populates="centre",
        cascade="all, delete-orphan",
    )
    bookings: Mapped[list[Booking]] = relationship(
        "Booking",
        back_populates="centre",
    )
