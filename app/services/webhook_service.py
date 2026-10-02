from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.logging_config import logger
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import WebhookPayload, WebhookResponse


class WebhookService:
    @staticmethod
    async def process_webhook(
        db: AsyncSession,
        payload: WebhookPayload,
    ) -> WebhookResponse:
        """Process payment provider webhooks idempotently with full concurrency safety."""
        # 1. Check if event_id has already been processed
        event_stmt = select(Payment).where(Payment.event_id == payload.event_id)
        event_res = await db.execute(event_stmt)
        existing_event_payment = event_res.scalar_one_or_none()

        if existing_event_payment:
            # Re-fetch booking status for response
            b_stmt = select(Booking).where(Booking.id == existing_event_payment.booking_id)
            b_res = await db.execute(b_stmt)
            existing_booking = b_res.scalar_one_or_none()
            current_booking_status = (
                existing_booking.status if existing_booking else BookingStatus.PENDING
            )

            # Exact match check across payload fields
            same_booking = existing_event_payment.booking_id == payload.booking_id
            same_provider_id = (
                existing_event_payment.provider_payment_id == payload.provider_payment_id
            )
            same_status = existing_event_payment.status == payload.status
            same_amount = existing_event_payment.amount == payload.amount

            if same_booking and same_provider_id and same_status and same_amount:
                logger.info(
                    "webhook_idempotent_duplicate_received",
                    event_id=payload.event_id,
                    provider_payment_id=payload.provider_payment_id,
                    booking_id=str(payload.booking_id),
                )
                return WebhookResponse(
                    status="success",
                    message="Webhook event has already been processed successfully (idempotent).",
                    idempotent=True,
                    payment_id=existing_event_payment.id,
                    booking_id=payload.booking_id,
                    booking_status=current_booking_status,
                )
            else:
                # Conflicting event payload with duplicate event_id
                logger.warning(
                    "webhook_conflicting_event_payload",
                    event_id=payload.event_id,
                    expected_booking=str(existing_event_payment.booking_id),
                    received_booking=str(payload.booking_id),
                )
                raise ConflictException(
                    detail="Event ID already exists with a different payload.",
                    code="EVENT_PAYLOAD_MISMATCH",
                )

        # 2. Check if provider_payment_id has already been used by another event
        provider_stmt = select(Payment).where(
            Payment.provider_payment_id == payload.provider_payment_id
        )
        provider_res = await db.execute(provider_stmt)
        if provider_res.scalar_one_or_none():
            logger.warning(
                "webhook_duplicate_provider_payment_id",
                provider_payment_id=payload.provider_payment_id,
            )
            raise ConflictException(
                detail="Provider payment ID has already been recorded under another event.",
                code="PROVIDER_PAYMENT_ID_EXISTS",
            )

        # 3. Lock booking row for safe transactional state transition
        booking_stmt = select(Booking).where(Booking.id == payload.booking_id).with_for_update()
        booking_res = await db.execute(booking_stmt)
        booking = booking_res.scalar_one_or_none()

        if not booking:
            logger.warning("webhook_unknown_booking", booking_id=str(payload.booking_id))
            raise NotFoundException(
                detail=f"Booking with ID {payload.booking_id} not found.",
                code="BOOKING_NOT_FOUND",
            )

        # Re-check if event_id was committed by another concurrent transaction while waiting for lock
        concurrent_event_stmt = select(Payment).where(Payment.event_id == payload.event_id)
        concurrent_event_res = await db.execute(concurrent_event_stmt)
        concurrent_payment = concurrent_event_res.scalar_one_or_none()
        if concurrent_payment:
            if (
                concurrent_payment.booking_id == payload.booking_id
                and concurrent_payment.provider_payment_id == payload.provider_payment_id
                and concurrent_payment.status == payload.status
                and concurrent_payment.amount == payload.amount
            ):
                logger.info("webhook_concurrent_duplicate_handled", event_id=payload.event_id)
                return WebhookResponse(
                    status="success",
                    message="Webhook event has already been processed successfully (idempotent).",
                    idempotent=True,
                    payment_id=concurrent_payment.id,
                    booking_id=payload.booking_id,
                    booking_status=booking.status,
                )
            raise ConflictException(
                detail="Event ID already exists with a different payload.",
                code="EVENT_PAYLOAD_MISMATCH",
            )

        # 4. Amount mismatch check
        if payload.amount != booking.amount:
            logger.warning(
                "webhook_amount_mismatch",
                booking_id=str(booking.id),
                booking_amount=str(booking.amount),
                payload_amount=str(payload.amount),
            )
            raise ConflictException(
                detail=f"Payment amount ({payload.amount}) does not match booking amount ({booking.amount}).",
                code="AMOUNT_MISMATCH",
            )

        # 5. Cancelled booking protection: never move CANCELLED to CONFIRMED or FAILED
        if booking.status == BookingStatus.CANCELLED:
            logger.warning(
                "webhook_rejected_on_cancelled_booking",
                booking_id=str(booking.id),
                event_id=payload.event_id,
            )
            raise ConflictException(
                detail="Cannot process payment webhook for a cancelled booking.",
                code="BOOKING_ALREADY_CANCELLED",
            )

        # 6. State transition protection against duplicate/stale events
        if booking.status == BookingStatus.CONFIRMED:
            raise ConflictException(
                detail="This booking has already been paid for and confirmed.",
                code="BOOKING_ALREADY_CONFIRMED",
            )
        if booking.status == BookingStatus.FAILED:
            raise ConflictException(
                detail="Cannot apply payment event to an already failed booking.",
                code="INVALID_STATE_TRANSITION",
            )

        # 7. Record payment
        new_payment = Payment(
            booking_id=booking.id,
            provider_payment_id=payload.provider_payment_id,
            event_id=payload.event_id,
            amount=payload.amount,
            status=payload.status,
        )
        db.add(new_payment)

        # 8. Update booking status
        if payload.status == PaymentStatus.SUCCESS:
            booking.status = BookingStatus.CONFIRMED
        else:
            booking.status = BookingStatus.FAILED

        try:
            await db.commit()
            await db.refresh(new_payment)
            await db.refresh(booking)
        except IntegrityError:
            await db.rollback()
            # Double check if duplicate race resolved via concurrent commit
            race_stmt = select(Payment).where(Payment.event_id == payload.event_id)
            race_res = await db.execute(race_stmt)
            race_payment = race_res.scalar_one_or_none()
            if (
                race_payment
                and race_payment.booking_id == payload.booking_id
                and race_payment.provider_payment_id == payload.provider_payment_id
                and race_payment.status == payload.status
                and race_payment.amount == payload.amount
            ):
                return WebhookResponse(
                    status="success",
                    message="Webhook event has already been processed successfully (idempotent).",
                    idempotent=True,
                    payment_id=race_payment.id,
                    booking_id=payload.booking_id,
                    booking_status=booking.status,
                )
            raise ConflictException(
                detail="Database constraint conflict during webhook payment processing.",
                code="PAYMENT_CONFLICT",
            ) from None

        logger.info(
            "webhook_processed_successfully",
            event_id=payload.event_id,
            payment_id=str(new_payment.id),
            booking_id=str(booking.id),
            booking_status=booking.status.value,
        )

        return WebhookResponse(
            status="success",
            message="Webhook event processed successfully.",
            idempotent=False,
            payment_id=new_payment.id,
            booking_id=booking.id,
            booking_status=booking.status,
        )
