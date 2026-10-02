import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.api.v1.health import router as health_router
from app.config import get_settings
from app.core.rate_limit import limiter, register_rate_limit_handlers
from app.database import async_engine
from app.exceptions import register_exception_handlers
from app.logging_config import logger, setup_logging
from app.services.cache_service import cache_service

settings = get_settings()
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info(
        "app_startup",
        project_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )
    yield
    # Shutdown actions
    logger.info("app_shutdown")
    await cache_service.close()
    await async_engine.dispose()


app = FastAPI(
    title="DiagPay API",
    version="1.0.0",
    description="Diagnostic Booking & Simulated Payment Backend for EVE Healthcare",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration, authentication and JWT tokens",
        },
        {
            "name": "Diagnostic Centres",
            "description": "Diagnostic centres management and test offerings",
        },
        {"name": "Diagnostic Tests", "description": "Diagnostic tests catalog and administration"},
        {
            "name": "Bookings",
            "description": "Diagnostic appointment bookings and lifecycle management",
        },
        {
            "name": "Payments",
            "description": "Simulated payment processing and idempotent webhook receiver",
        },
        {"name": "Health", "description": "System readiness and service health checks"},
    ],
)

# Attach SlowAPI limiter state
app.state.limiter = limiter
register_rate_limit_handlers(app)

# Register uniform error responses
register_exception_handlers(app)

# CORS Middleware
origins = (
    settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def structlog_request_middleware(request: Request, call_next):
    """Enrich logging context with correlation ID and compute request duration."""
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
    )

    start_time = time.perf_counter()
    logger.info("request_started")

    try:
        response = await call_next(request)
        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms}ms"

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=process_time_ms,
        )
        return response
    except Exception as exc:
        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "request_failed",
            duration_ms=process_time_ms,
            error=str(exc),
        )
        raise exc


# Mount Routers
app.include_router(api_v1_router)
app.include_router(health_router)  # Accessible directly at /health
