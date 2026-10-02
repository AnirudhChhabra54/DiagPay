import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.test import TestCreate, TestResponse, TestUpdate
from app.services.test_service import TestService

router = APIRouter(prefix="/tests", tags=["Diagnostic Tests"])


@router.get(
    "",
    response_model=PaginatedResponse[TestResponse],
    status_code=status.HTTP_200_OK,
    summary="List diagnostic tests",
    description="Retrieve a paginated list of catalog diagnostic tests (cached in Redis).",
)
async def list_tests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    active_only: bool = Query(True, description="Filter only active tests"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[TestResponse]:
    return await TestService.list_tests(
        db=db,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )


@router.get(
    "/{test_id}",
    response_model=TestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get diagnostic test by ID",
    description="Retrieve catalog test details by UUID.",
)
async def get_test(
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestResponse:
    test = await TestService.get_by_id(db, test_id)
    return TestResponse.model_validate(test)


@router.post(
    "",
    response_model=TestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create diagnostic test (Admin only)",
    description="Registers a new diagnostic test in the catalog.",
)
async def create_test(
    payload: TestCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TestResponse:
    test = await TestService.create(db, payload)
    return TestResponse.model_validate(test)


@router.patch(
    "/{test_id}",
    response_model=TestResponse,
    status_code=status.HTTP_200_OK,
    summary="Update diagnostic test (Admin only)",
    description="Updates catalog test details.",
)
async def update_test(
    test_id: uuid.UUID,
    payload: TestUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TestResponse:
    test = await TestService.update(db, test_id, payload)
    return TestResponse.model_validate(test)


@router.delete(
    "/{test_id}",
    response_model=TestResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate diagnostic test (Admin only)",
    description="Soft-deletes/deactivates a diagnostic test.",
)
async def delete_test(
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TestResponse:
    test = await TestService.delete(db, test_id)
    return TestResponse.model_validate(test)
