import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User, UserRole
from app.services.cache_service import cache_service

# In-memory async SQLite engine for isolated, fast, deterministic testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def prepare_database():
    """Create all tables before each test and drop them after."""
    # Ensure cache is flushed or mocked
    await cache_service.invalidate_patterns("*")

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncSession:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    admin = User(
        id=uuid.uuid4(),
        email="admin@diagpay.com",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="user@diagpay.com",
        password_hash=hash_password("UserPass123!"),
        full_name="John Doe",
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="other@diagpay.com",
        password_hash=hash_password("UserPass123!"),
        full_name="Alice Smith",
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(subject=str(admin_user.id), role=admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(regular_user: User) -> dict[str, str]:
    token = create_access_token(subject=str(regular_user.id), role=regular_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user_headers(other_user: User) -> dict[str, str]:
    token = create_access_token(subject=str(other_user.id), role=other_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sample_centre(db_session: AsyncSession) -> DiagnosticCentre:
    centre = DiagnosticCentre(
        id=uuid.uuid4(),
        name="Apex Diagnostics",
        location="123 Health Ave, Metropolis",
        is_active=True,
    )
    db_session.add(centre)
    await db_session.commit()
    await db_session.refresh(centre)
    return centre


@pytest.fixture
async def sample_test(db_session: AsyncSession) -> DiagnosticTest:
    test = DiagnosticTest(
        id=uuid.uuid4(),
        name="Complete Blood Count",
        description="Routine hematology blood test",
        is_active=True,
    )
    db_session.add(test)
    await db_session.commit()
    await db_session.refresh(test)
    return test


@pytest.fixture
async def sample_centre_test(
    db_session: AsyncSession,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
) -> CentreTest:
    ct = CentreTest(
        id=uuid.uuid4(),
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        price=Decimal("450.00"),
        is_available=True,
    )
    db_session.add(ct)
    await db_session.commit()
    await db_session.refresh(ct)
    return ct


@pytest.fixture
async def sample_booking(
    db_session: AsyncSession,
    regular_user: User,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
    sample_centre_test: CentreTest,
) -> Booking:
    appointment_time = datetime.now(UTC) + timedelta(days=2)
    booking = Booking(
        id=uuid.uuid4(),
        user_id=regular_user.id,
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        appointment_at=appointment_time,
        amount=sample_centre_test.price,
        status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)
    return booking
