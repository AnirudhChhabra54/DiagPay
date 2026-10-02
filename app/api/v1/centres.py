import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.centre import CentreCreate, CentreResponse, CentreUpdate
from app.schemas.centre_test import (
    CentreTestCreate,
    CentreTestDetailResponse,
    CentreTestResponse,
    CentreTestUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.centre_service import CentreService
from app.services.test_service import TestService

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get(
    "",
    response_model=PaginatedResponse[CentreResponse],
    status_code=status.HTTP_200_OK,
    summary="List diagnostic centres",
    description="Retrieve a paginated list of diagnostic centres (cached in Redis).",
)
async def list_centres(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    active_only: bool = Query(True, description="Filter only active centres"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[CentreResponse]:
    return await CentreService.list_centres(
        db=db,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )


@router.get(
    "/{centre_id}",
    response_model=CentreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get diagnostic centre by ID",
    description="Retrieve details for a specific diagnostic centre.",
)
async def get_centre(
    centre_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CentreResponse:
    centre = await CentreService.get_by_id(db, centre_id)
    return CentreResponse.model_validate(centre)


@router.post(
    "",
    response_model=CentreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create diagnostic centre (Admin only)",
    description="Creates a new diagnostic centre and invalidates cached centre listings.",
)
async def create_centre(
    payload: CentreCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CentreResponse:
    centre = await CentreService.create(db, payload)
    return CentreResponse.model_validate(centre)


@router.patch(
    "/{centre_id}",
    response_model=CentreResponse,
    status_code=status.HTTP_200_OK,
    summary="Update diagnostic centre (Admin only)",
    description="Updates diagnostic centre information and invalidates caches.",
)
async def update_centre(
    centre_id: uuid.UUID,
    payload: CentreUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CentreResponse:
    centre = await CentreService.update(db, centre_id, payload)
    return CentreResponse.model_validate(centre)


@router.delete(
    "/{centre_id}",
    response_model=CentreResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate diagnostic centre (Admin only)",
    description="Soft-deletes/deactivates a diagnostic centre.",
)
async def delete_centre(
    centre_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CentreResponse:
    centre = await CentreService.delete(db, centre_id)
    return CentreResponse.model_validate(centre)


@router.get(
    "/{centre_id}/tests",
    response_model=list[CentreTestDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="List tests available at diagnostic centre",
    description="Retrieve all diagnostic tests offered by this centre with centre-specific pricing.",
)
async def list_centre_tests(
    centre_id: uuid.UUID,
    active_only: bool = Query(True, description="Filter only available tests"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CentreTestDetailResponse]:
    return await CentreService.get_centre_tests(db, centre_id, active_only=active_only)


@router.post(
    "/{centre_id}/tests",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or update test pricing at centre (Admin only)",
    description="Assigns a diagnostic test to a centre with custom pricing and availability.",
)
async def add_centre_test(
    centre_id: uuid.UUID,
    payload: CentreTestCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CentreTestResponse:
    mapping = await TestService.add_or_update_centre_test(db, centre_id, payload)
    return CentreTestResponse.model_validate(mapping)


@router.patch(
    "/{centre_id}/tests/{test_id}",
    response_model=CentreTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Update test pricing or availability at centre (Admin only)",
    description="Updates pricing or availability of an existing test mapping.",
)
async def update_centre_test(
    centre_id: uuid.UUID,
    test_id: uuid.UUID,
    payload: CentreTestUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> CentreTestResponse:
    mapping = await TestService.update_centre_test(db, centre_id, test_id, payload)
    return CentreTestResponse.model_validate(mapping)


@router.delete(
    "/{centre_id}/tests/{test_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove test offering from centre (Admin only)",
    description="Removes the test mapping from the centre.",
)
async def delete_centre_test(
    centre_id: uuid.UUID,
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageResponse:
    await TestService.delete_centre_test(db, centre_id, test_id)
    return MessageResponse(message="Test offering removed from diagnostic centre.")
