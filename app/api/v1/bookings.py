import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.booking import BookingStatus
from app.models.user import User
from app.schemas.booking import (
    BookingCancelResponse,
    BookingCreate,
    BookingResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create diagnostic test booking",
    description="Books a diagnostic test at a centre for a future appointment date. Validates centre, test, and active availability, and captures a snapshot of current test pricing.",
)
async def create_booking(
    payload: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    booking = await BookingService.create_booking(db, current_user, payload)
    return BookingResponse.model_validate(booking)


@router.get(
    "",
    response_model=PaginatedResponse[BookingResponse],
    status_code=status.HTTP_200_OK,
    summary="List bookings",
    description="Retrieve bookings. Regular users only see their own bookings; administrators see all bookings.",
)
async def list_bookings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: BookingStatus | None = Query(None, description="Optional booking status filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[BookingResponse]:
    return await BookingService.list_bookings(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get booking details",
    description="Retrieve specific booking details by ID. Users can only access their own bookings unless they are administrators.",
)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    booking = await BookingService.get_booking_by_id(db, booking_id, current_user)
    return BookingResponse.model_validate(booking)


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel booking",
    description="Cancels an existing booking. Only the owner or an administrator can cancel. Idempotent if already cancelled.",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingCancelResponse:
    booking = await BookingService.cancel_booking(db, booking_id, current_user)
    return BookingCancelResponse(
        id=booking.id,
        status=booking.status,
        message="Booking has been cancelled successfully.",
    )
