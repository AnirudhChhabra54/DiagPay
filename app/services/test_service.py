import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.logging_config import logger
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.schemas.centre_test import CentreTestCreate, CentreTestUpdate
from app.schemas.common import PaginatedResponse
from app.schemas.test import TestCreate, TestResponse, TestUpdate
from app.services.cache_service import cache_service


class TestService:
    @staticmethod
    async def list_tests(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> PaginatedResponse[TestResponse]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        cache_key = f"tests:list:p{page}:s{page_size}:act{active_only}"
        cached = await cache_service.get(cache_key)
        if cached:
            return PaginatedResponse[TestResponse](**cached)

        query = select(DiagnosticTest)
        count_query = select(func.count(DiagnosticTest.id))
        if active_only:
            query = query.where(DiagnosticTest.is_active.is_(True))
            count_query = count_query.where(DiagnosticTest.is_active.is_(True))

        total_res = await db.execute(count_query)
        total = total_res.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(DiagnosticTest.name.asc()).offset(offset).limit(page_size)
        res = await db.execute(query)
        tests = res.scalars().all()

        items = [TestResponse.model_validate(t) for t in tests]
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        result = PaginatedResponse[TestResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

        await cache_service.set(cache_key, result.model_dump())
        return result

    @staticmethod
    async def get_by_id(db: AsyncSession, test_id: uuid.UUID) -> DiagnosticTest:
        cache_key = f"tests:{test_id}"
        cached = await cache_service.get(cache_key)
        if cached:
            return DiagnosticTest(**cached)

        stmt = select(DiagnosticTest).where(DiagnosticTest.id == test_id)
        res = await db.execute(stmt)
        test = res.scalar_one_or_none()
        if not test:
            raise NotFoundException(
                detail=f"Diagnostic test with ID {test_id} not found.",
                code="TEST_NOT_FOUND",
            )
        await cache_service.set(
            cache_key,
            TestResponse.model_validate(test).model_dump(),
        )
        return test

    @staticmethod
    async def create(db: AsyncSession, payload: TestCreate) -> DiagnosticTest:
        test = DiagnosticTest(
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            is_active=payload.is_active,
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        await cache_service.invalidate_patterns("tests:*")
        logger.info("test_created", test_id=str(test.id), name=test.name)
        return test

    @staticmethod
    async def update(
        db: AsyncSession,
        test_id: uuid.UUID,
        payload: TestUpdate,
    ) -> DiagnosticTest:
        test = await TestService.get_by_id(db, test_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(test, key, value)

        await db.commit()
        await db.refresh(test)
        await cache_service.invalidate_patterns("tests:*", "centres:*:tests*")
        logger.info("test_updated", test_id=str(test.id))
        return test

    @staticmethod
    async def delete(db: AsyncSession, test_id: uuid.UUID) -> DiagnosticTest:
        """Deactivate diagnostic test (soft delete to preserve history)."""
        test = await TestService.get_by_id(db, test_id)
        test.is_active = False
        await db.commit()
        await db.refresh(test)
        await cache_service.invalidate_patterns("tests:*", "centres:*:tests*")
        logger.info("test_deactivated", test_id=str(test.id))
        return test

    @staticmethod
    async def add_or_update_centre_test(
        db: AsyncSession,
        centre_id: uuid.UUID,
        payload: CentreTestCreate,
    ) -> CentreTest:
        # Check centre exists
        centre_stmt = select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
        centre_res = await db.execute(centre_stmt)
        if not centre_res.scalar_one_or_none():
            raise NotFoundException(
                detail=f"Diagnostic centre with ID {centre_id} not found.",
                code="CENTRE_NOT_FOUND",
            )

        # Check test exists
        await TestService.get_by_id(db, payload.test_id)

        # Check if mapping already exists
        mapping_stmt = select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == payload.test_id,
        )
        mapping_res = await db.execute(mapping_stmt)
        mapping = mapping_res.scalar_one_or_none()

        if mapping:
            # Update existing mapping
            mapping.price = payload.price
            mapping.is_available = payload.is_available
        else:
            # Create new mapping
            mapping = CentreTest(
                centre_id=centre_id,
                test_id=payload.test_id,
                price=payload.price,
                is_available=payload.is_available,
            )
            db.add(mapping)

        await db.commit()
        await db.refresh(mapping)
        await cache_service.invalidate_patterns("centres:*:tests*", f"centres:{centre_id}*")
        logger.info(
            "centre_test_mapping_saved",
            centre_id=str(centre_id),
            test_id=str(payload.test_id),
            price=str(payload.price),
        )
        return mapping

    @staticmethod
    async def update_centre_test(
        db: AsyncSession,
        centre_id: uuid.UUID,
        test_id: uuid.UUID,
        payload: CentreTestUpdate,
    ) -> CentreTest:
        mapping_stmt = select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
        mapping_res = await db.execute(mapping_stmt)
        mapping = mapping_res.scalar_one_or_none()
        if not mapping:
            raise NotFoundException(
                detail="Test mapping for this diagnostic centre was not found.",
                code="CENTRE_TEST_NOT_FOUND",
            )

        if payload.price is not None:
            mapping.price = payload.price
        if payload.is_available is not None:
            mapping.is_available = payload.is_available

        await db.commit()
        await db.refresh(mapping)
        await cache_service.invalidate_patterns("centres:*:tests*", f"centres:{centre_id}*")
        return mapping

    @staticmethod
    async def delete_centre_test(
        db: AsyncSession,
        centre_id: uuid.UUID,
        test_id: uuid.UUID,
    ) -> None:
        mapping_stmt = select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
        mapping_res = await db.execute(mapping_stmt)
        mapping = mapping_res.scalar_one_or_none()
        if not mapping:
            raise NotFoundException(
                detail="Test mapping for this diagnostic centre was not found.",
                code="CENTRE_TEST_NOT_FOUND",
            )

        await db.delete(mapping)
        await db.commit()
        await cache_service.invalidate_patterns("centres:*:tests*", f"centres:{centre_id}*")
        logger.info("centre_test_mapping_deleted", centre_id=str(centre_id), test_id=str(test_id))
