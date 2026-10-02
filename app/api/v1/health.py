from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.logging_config import logger
from app.services.cache_service import cache_service

settings = get_settings()
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Check the operational readiness of the API, Database, and Redis services.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_status = "connected"
    redis_status = "connected"
    overall_status = "healthy"

    # 1. Check PostgreSQL database connectivity
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        db_status = f"disconnected: {str(e)}"
        overall_status = "unhealthy"

    # 2. Check Redis cache connectivity
    try:
        redis_alive = await cache_service.ping()
        if not redis_alive:
            redis_status = "degraded (unreachable or disabled)"
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        logger.warning("health_check_redis_failed", error=str(e))
        redis_status = f"degraded: {str(e)}"
        if overall_status == "healthy":
            overall_status = "degraded"

    http_status = (
        status.HTTP_200_OK
        if overall_status in ("healthy", "degraded")
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": settings.ENVIRONMENT,
            "services": {
                "api": "healthy",
                "database": db_status,
                "redis": redis_status,
            },
        },
    )
