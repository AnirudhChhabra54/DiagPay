import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.logging_config import logger
from app.models.booking import Booking, BookingStatus
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, BookingResponse
from app.schemas.common import PaginatedResponse


class BookingService:
    @staticmethod
    async def create_booking(
        db: AsyncSession,
        user: User,
        payload: BookingCreate,
    ) -> Booking:
        now = datetime.now(UTC)
        appointment_utc = (
            payload.appointment_at
            if payload.appointment_at.tzinfo
            else payload.appointment_at.replace(tzinfo=UTC)
        )

        if appointment_utc <= now:
            raise AppException(
                detail="Appointment must be scheduled for a future time.",
                code="INVALID_APPOINTMENT_TIME",
                status_code=400,
            )

        # 1. Centre must exist and be active
        centre_stmt = select(DiagnosticCentre).where(DiagnosticCentre.id == payload.centre_id)
        centre_res = await db.execute(centre_stmt)
        centre = centre_res.scalar_one_or_none()
        if not centre:
            raise NotFoundException(
                detail=f"Diagnostic centre with ID {payload.centre_id} not found.",
                code="CENTRE_NOT_FOUND",
            )
        if not centre.is_active:
            raise AppException(
                detail="The selected diagnostic centre is currently inactive.",
                code="CENTRE_INACTIVE",
                status_code=400,
            )

        # 2. Test must exist and be active
        test_stmt = select(DiagnosticTest).where(DiagnosticTest.id == payload.test_id)
        test_res = await db.execute(test_stmt)
        test = test_res.scalar_one_or_none()
        if not test:
            raise NotFoundException(
                detail=f"Diagnostic test with ID {payload.test_id} not found.",
                code="TEST_NOT_FOUND",
            )
        if not test.is_active:
            raise AppException(
                detail="The selected diagnostic test is currently inactive.",
                code="TEST_INACTIVE",
                status_code=400,
            )

        # 3. Test must be offered and available at the centre
        mapping_stmt = select(CentreTest).where(
            CentreTest.centre_id == payload.centre_id,
            CentreTest.test_id == payload.test_id,
        )
        mapping_res = await db.execute(mapping_stmt)
        mapping = mapping_res.scalar_one_or_none()
        if not mapping:
            raise NotFoundException(
                detail="This test is not offered at the selected diagnostic centre.",
                code="TEST_NOT_OFFERED",
            )
        if not mapping.is_available:
            raise AppException(
                detail="This test is currently marked as unavailable at the selected diagnostic centre.",
                code="TEST_UNAVAILABLE",
                status_code=400,
            )

        # 4. Prevent duplicate active booking for same user/test/centre/slot
        dup_stmt = select(Booking).where(
            Booking.user_id == user.id,
            Booking.centre_id == payload.centre_id,
            Booking.test_id == payload.test_id,
            Booking.appointment_at == appointment_utc,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
        )
        dup_res = await db.execute(dup_stmt)
        if dup_res.scalar_one_or_none():
            logger.warning(
                "duplicate_booking_attempt",
                user_id=str(user.id),
                centre_id=str(payload.centre_id),
                test_id=str(payload.test_id),
                appointment_at=str(appointment_utc),
            )
            raise ConflictException(
                detail="An active booking already exists for this diagnostic test and time slot.",
                code="DUPLICATE_BOOKING",
            )

        # 5. Create booking with price snapshot from CentreTest
        booking = Booking(
            user_id=user.id,
            centre_id=payload.centre_id,
            test_id=payload.test_id,
            appointment_at=appointment_utc,
            amount=mapping.price,
            status=BookingStatus.PENDING,
        )
        db.add(booking)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.warning(
                "concurrent_duplicate_booking_collision",
                user_id=str(user.id),
                centre_id=str(payload.centre_id),
                test_id=str(payload.test_id),
                appointment_at=str(appointment_utc),
            )
            raise ConflictException(
                detail="An active booking already exists for this diagnostic test and time slot.",
                code="DUPLICATE_BOOKING",
            ) from None

        # Eager load relationships for response
        stmt = (
            select(Booking)
            .where(Booking.id == booking.id)
            .options(selectinload(Booking.centre), selectinload(Booking.test))
        )
        res = await db.execute(stmt)
        booking = res.scalar_one()

        logger.info(
            "booking_created",
            booking_id=str(booking.id),
            user_id=str(user.id),
            amount=str(booking.amount),
            status=booking.status.value,
        )
        return booking

    @staticmethod
    async def list_bookings(
        db: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
        status_filter: BookingStatus | None = None,
    ) -> PaginatedResponse[BookingResponse]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        query = select(Booking).options(selectinload(Booking.centre), selectinload(Booking.test))
        count_query = select(func.count(Booking.id))

        # Enforce data access isolation: regular users only see their own bookings
        if user.role != UserRole.ADMIN:
            query = query.where(Booking.user_id == user.id)
            count_query = count_query.where(Booking.user_id == user.id)

        if status_filter:
            query = query.where(Booking.status == status_filter)
            count_query = count_query.where(Booking.status == status_filter)

        total_res = await db.execute(count_query)
        total = total_res.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(Booking.created_at.desc()).offset(offset).limit(page_size)
        res = await db.execute(query)
        bookings = res.scalars().all()

        items = [BookingResponse.model_validate(b) for b in bookings]
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedResponse[BookingResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_booking_by_id(
        db: AsyncSession,
        booking_id: uuid.UUID,
        user: User,
    ) -> Booking:
        stmt = (
            select(Booking)
            .where(Booking.id == booking_id)
            .options(selectinload(Booking.centre), selectinload(Booking.test))
        )
        res = await db.execute(stmt)
        booking = res.scalar_one_or_none()
        if not booking:
            raise NotFoundException(
                detail=f"Booking with ID {booking_id} not found.",
                code="BOOKING_NOT_FOUND",
            )

        # Enforce user isolation: non-admins cannot access other users' bookings
        if user.role != UserRole.ADMIN and booking.user_id != user.id:
            raise ForbiddenException(
                detail="You do not have permission to view this booking.",
                code="FORBIDDEN_ACCESS",
            )
        return booking

    @staticmethod
    async def cancel_booking(
        db: AsyncSession,
        booking_id: uuid.UUID,
        user: User,
    ) -> Booking:
        """Cancel a booking with row locking and idempotency."""
        # Row lock using with_for_update to avoid concurrent race conditions
        stmt = select(Booking).where(Booking.id == booking_id).with_for_update()
        res = await db.execute(stmt)
        booking = res.scalar_one_or_none()
        if not booking:
            raise NotFoundException(
                detail=f"Booking with ID {booking_id} not found.",
                code="BOOKING_NOT_FOUND",
            )

        if user.role != UserRole.ADMIN and booking.user_id != user.id:
            raise ForbiddenException(
                detail="You do not have permission to cancel this booking.",
                code="FORBIDDEN_ACCESS",
            )

        # Idempotency check: if already cancelled, return existing state
        if booking.status == BookingStatus.CANCELLED:
            logger.info("booking_cancel_idempotent", booking_id=str(booking_id))
            return booking

        if booking.status == BookingStatus.CONFIRMED:
            raise ConflictException(
                detail="Cannot cancel a booking that has already been confirmed and paid.",
                code="BOOKING_ALREADY_CONFIRMED",
            )

        if booking.status == BookingStatus.FAILED:
            raise ConflictException(
                detail="Cannot cancel a booking that has already failed.",
                code="INVALID_STATE_TRANSITION",
            )

        # Apply cancellation
        booking.status = BookingStatus.CANCELLED
        await db.commit()
        await db.refresh(booking)

        logger.info(
            "booking_cancelled",
            booking_id=str(booking_id),
            user_id=str(user.id),
        )
        return booking
