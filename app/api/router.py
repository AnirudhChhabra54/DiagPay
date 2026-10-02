from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.centres import router as centres_router
from app.api.v1.health import router as health_router
from app.api.v1.payments import router as payments_router
from app.api.v1.tests import router as tests_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(centres_router)
api_v1_router.include_router(tests_router)
api_v1_router.include_router(bookings_router)
api_v1_router.include_router(payments_router)
api_v1_router.include_router(health_router)
