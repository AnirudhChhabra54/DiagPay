import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.logging_config import logger
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.payment import PaymentResponse, PaymentSimulateRequest


class PaymentService:
    @staticmethod
    async def process_simulated_payment(
        db: AsyncSession,
        user: User,
        payload: PaymentSimulateRequest,
    ) -> PaymentResponse:
        """Process a simulated payment against a booking with strict concurrency protection."""
        # Row-lock booking for transactional update
        stmt = select(Booking).where(Booking.id == payload.booking_id).with_for_update()
        res = await db.execute(stmt)
        booking = res.scalar_one_or_none()

        if not booking:
            raise NotFoundException(
                detail=f"Booking with ID {payload.booking_id} not found.",
                code="BOOKING_NOT_FOUND",
            )

        # Enforce user authorization: only booking owner or admin can initiate payment
        if user.role != UserRole.ADMIN and booking.user_id != user.id:
            raise ForbiddenException(
                detail="You do not have permission to pay for this booking.",
                code="FORBIDDEN_ACCESS",
            )

        # Reject cancelled bookings
        if booking.status == BookingStatus.CANCELLED:
            raise ConflictException(
                detail="Cannot process payment for a cancelled booking.",
                code="BOOKING_ALREADY_CANCELLED",
            )

        # Reject already paid bookings
        if booking.status == BookingStatus.CONFIRMED:
            raise ConflictException(
                detail="This booking has already been paid for and confirmed.",
                code="BOOKING_ALREADY_CONFIRMED",
            )

        # Reject already failed bookings
        if booking.status == BookingStatus.FAILED:
            raise ConflictException(
                detail="Cannot process payment for a booking that has already failed.",
                code="BOOKING_ALREADY_FAILED",
            )

        # Generate unique simulation IDs
        provider_payment_id = f"sim_pay_{uuid.uuid4().hex[:16]}"
        event_id = f"evt_sim_{uuid.uuid4().hex[:16]}"

        payment = Payment(
            booking_id=booking.id,
            provider_payment_id=provider_payment_id,
            event_id=event_id,
            amount=booking.amount,
            status=payload.simulate_result,
        )
        db.add(payment)

        # Update booking state based on simulation result
        if payload.simulate_result == PaymentStatus.SUCCESS:
            booking.status = BookingStatus.CONFIRMED
        else:
            booking.status = BookingStatus.FAILED

        await db.commit()
        await db.refresh(payment)
        await db.refresh(booking)

        logger.info(
            "payment_simulated",
            payment_id=str(payment.id),
            booking_id=str(booking.id),
            status=payment.status.value,
            provider_payment_id=provider_payment_id,
            amount=str(payment.amount),
        )

        return PaymentResponse(
            id=payment.id,
            booking_id=payment.booking_id,
            provider_payment_id=payment.provider_payment_id,
            event_id=payment.event_id,
            amount=payment.amount,
            status=payment.status,
            booking_status=booking.status,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )
