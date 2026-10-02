import redis as sync_redis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.logging_config import logger

settings = get_settings()


def get_limiter_storage_uri() -> str:
    """Determine rate limiter storage with graceful in-memory fallback."""
    if settings.ENVIRONMENT in ("test", "testing") or not settings.REDIS_ENABLED:
        return "memory://"
    try:
        r = sync_redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        r.ping()
        return settings.REDIS_URL
    except Exception as e:
        logger.warning(
            "redis_unavailable_for_rate_limiter_fallback_to_memory",
            error=str(e),
        )
        return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=get_limiter_storage_uri(),
    strategy="fixed-window",
)


def register_rate_limit_handlers(app: FastAPI) -> None:
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        logger.warning(
            "rate_limit_exceeded",
            ip=request.client.host if request.client else "unknown",
            path=request.url.path,
            detail=str(exc.detail),
        )
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded: {exc.detail}",
                "code": "RATE_LIMIT_EXCEEDED",
            },
        )
