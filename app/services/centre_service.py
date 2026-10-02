import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundException
from app.logging_config import logger
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.schemas.centre import CentreCreate, CentreResponse, CentreUpdate
from app.schemas.centre_test import CentreTestDetailResponse
from app.schemas.common import PaginatedResponse
from app.services.cache_service import cache_service


class CentreService:
    @staticmethod
    async def list_centres(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> PaginatedResponse[CentreResponse]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        cache_key = f"centres:list:p{page}:s{page_size}:act{active_only}"
        cached = await cache_service.get(cache_key)
        if cached:
            return PaginatedResponse[CentreResponse](**cached)

        query = select(DiagnosticCentre)
        count_query = select(func.count(DiagnosticCentre.id))
        if active_only:
            query = query.where(DiagnosticCentre.is_active.is_(True))
            count_query = count_query.where(DiagnosticCentre.is_active.is_(True))

        total_res = await db.execute(count_query)
        total = total_res.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(DiagnosticCentre.name.asc()).offset(offset).limit(page_size)
        res = await db.execute(query)
        centres = res.scalars().all()

        items = [CentreResponse.model_validate(c) for c in centres]
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        result = PaginatedResponse[CentreResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

        await cache_service.set(cache_key, result.model_dump())
        return result

    @staticmethod
    async def get_by_id(db: AsyncSession, centre_id: uuid.UUID) -> DiagnosticCentre:
        cache_key = f"centres:{centre_id}"
        cached = await cache_service.get(cache_key)
        if cached:
            return DiagnosticCentre(**cached)

        stmt = select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
        res = await db.execute(stmt)
        centre = res.scalar_one_or_none()
        if not centre:
            raise NotFoundException(
                detail=f"Diagnostic centre with ID {centre_id} not found.",
                code="CENTRE_NOT_FOUND",
            )
        await cache_service.set(
            cache_key,
            CentreResponse.model_validate(centre).model_dump(),
        )
        return centre

    @staticmethod
    async def create(db: AsyncSession, payload: CentreCreate) -> DiagnosticCentre:
        centre = DiagnosticCentre(
            name=payload.name.strip(),
            location=payload.location.strip(),
            is_active=payload.is_active,
        )
        db.add(centre)
        await db.commit()
        await db.refresh(centre)
        await cache_service.invalidate_patterns("centres:*")
        logger.info("centre_created", centre_id=str(centre.id), name=centre.name)
        return centre

    @staticmethod
    async def update(
        db: AsyncSession,
        centre_id: uuid.UUID,
        payload: CentreUpdate,
    ) -> DiagnosticCentre:
        centre = await CentreService.get_by_id(db, centre_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(centre, key, value)

        await db.commit()
        await db.refresh(centre)
        await cache_service.invalidate_patterns("centres:*")
        logger.info("centre_updated", centre_id=str(centre.id))
        return centre

    @staticmethod
    async def delete(db: AsyncSession, centre_id: uuid.UUID) -> DiagnosticCentre:
        """Deactivate diagnostic centre (soft delete to preserve historical booking records)."""
        centre = await CentreService.get_by_id(db, centre_id)
        centre.is_active = False
        await db.commit()
        await db.refresh(centre)
        await cache_service.invalidate_patterns("centres:*")
        logger.info("centre_deactivated", centre_id=str(centre.id))
        return centre

    @staticmethod
    async def get_centre_tests(
        db: AsyncSession,
        centre_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[CentreTestDetailResponse]:
        # Verify centre exists
        await CentreService.get_by_id(db, centre_id)

        cache_key = f"centres:{centre_id}:tests:act{active_only}"
        cached = await cache_service.get(cache_key)
        if cached:
            return [CentreTestDetailResponse(**item) for item in cached]

        stmt = (
            select(CentreTest)
            .join(DiagnosticTest, CentreTest.test_id == DiagnosticTest.id)
            .where(CentreTest.centre_id == centre_id)
            .options(selectinload(CentreTest.test))
        )
        if active_only:
            stmt = stmt.where(
                CentreTest.is_available.is_(True),
                DiagnosticTest.is_active.is_(True),
            )

        res = await db.execute(stmt)
        centre_tests = res.scalars().all()

        details = [
            CentreTestDetailResponse(
                id=ct.id,
                test_id=ct.test_id,
                test_name=ct.test.name,
                description=ct.test.description,
                price=ct.price,
                is_available=ct.is_available,
            )
            for ct in centre_tests
        ]

        await cache_service.set(
            cache_key,
            [d.model_dump() for d in details],
        )
        return details
