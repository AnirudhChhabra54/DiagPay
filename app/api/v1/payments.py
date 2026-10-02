from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.dependencies import get_current_user, verify_webhook_signature
from app.models.user import User
from app.schemas.payment import (
    PaymentResponse,
    PaymentSimulateRequest,
    WebhookPayload,
    WebhookResponse,
)
from app.services.payment_service import PaymentService
from app.services.webhook_service import WebhookService

settings = get_settings()
router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate payment for booking",
    description="Simulates a payment attempt (SUCCESS or FAILED) for a booking. Confirms or fails the booking atomically.",
)
@limiter.limit(settings.RATE_LIMIT_PAYMENT)
async def process_simulated_payment(
    request: Request,
    payload: PaymentSimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentResponse:
    return await PaymentService.process_simulated_payment(
        db=db,
        user=current_user,
        payload=payload,
    )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_webhook_signature)],
    summary="Process payment provider webhook",
    description="Idempotent webhook endpoint for processing payment notifications from external payment providers.",
)
@limiter.limit(settings.RATE_LIMIT_WEBHOOK)
async def process_webhook(
    request: Request,
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    return await WebhookService.process_webhook(
        db=db,
        payload=payload,
    )
