import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.logging_config import logger
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User, UserRole


async def seed_database(db: AsyncSession) -> None:
    """Seed initial data idempotently for development and testing."""
    logger.info("seeding_database_started")

    # 1. Seed Users
    users_data = [
        {
            "email": "admin@diagpay.com",
            "password": "AdminPass123!",
            "full_name": "DiagPay System Administrator",
            "role": UserRole.ADMIN,
        },
        {
            "email": "user@diagpay.com",
            "password": "UserPass123!",
            "full_name": "Jane Doe",
            "role": UserRole.USER,
        },
    ]

    for u in users_data:
        stmt = select(User).where(User.email == u["email"])
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            user = User(
                email=u["email"],
                password_hash=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
            )
            db.add(user)
            logger.info("seeded_user", email=u["email"], role=u["role"].value)

    await db.commit()

    # 2. Seed Diagnostic Centres
    centres_data = [
        {"name": "Apex Diagnostic Hub", "location": "742 Evergreen Terrace, Springfield"},
        {"name": "Metro PathLabs", "location": "100 Baker Street, London"},
        {"name": "Suburban Health Care", "location": "42 Wallaby Way, Sydney"},
    ]

    centres_map: dict[str, DiagnosticCentre] = {}
    for c in centres_data:
        stmt = select(DiagnosticCentre).where(DiagnosticCentre.name == c["name"])
        res = await db.execute(stmt)
        centre = res.scalar_one_or_none()
        if not centre:
            centre = DiagnosticCentre(name=c["name"], location=c["location"], is_active=True)
            db.add(centre)
            await db.flush()
            logger.info("seeded_centre", name=c["name"])
        centres_map[c["name"]] = centre

    await db.commit()

    # 3. Seed Diagnostic Tests
    tests_data = [
        {
            "name": "Complete Blood Count (CBC)",
            "description": "Evaluates overall health and detects a variety of disorders like anemia and infection.",
        },
        {
            "name": "Lipid Profile",
            "description": "Comprehensive panel measuring total cholesterol, HDL, LDL, and triglycerides.",
        },
        {
            "name": "Liver Function Test (LFT)",
            "description": "Measures enzymes, proteins, and bilirubin levels in the blood to evaluate liver health.",
        },
        {
            "name": "HbA1c Diabetes Screen",
            "description": "Measures average blood sugar levels over the preceding 2 to 3 months.",
        },
    ]

    tests_map: dict[str, DiagnosticTest] = {}
    for t in tests_data:
        stmt = select(DiagnosticTest).where(DiagnosticTest.name == t["name"])
        res = await db.execute(stmt)
        test = res.scalar_one_or_none()
        if not test:
            test = DiagnosticTest(name=t["name"], description=t["description"], is_active=True)
            db.add(test)
            await db.flush()
            logger.info("seeded_test", name=t["name"])
        tests_map[t["name"]] = test

    await db.commit()

    # 4. Seed Centre-Test Mappings with Centre-specific Pricing
    mappings = [
        # Apex Diagnostic Hub
        ("Apex Diagnostic Hub", "Complete Blood Count (CBC)", Decimal("350.00")),
        ("Apex Diagnostic Hub", "Lipid Profile", Decimal("800.00")),
        ("Apex Diagnostic Hub", "Liver Function Test (LFT)", Decimal("900.00")),
        ("Apex Diagnostic Hub", "HbA1c Diabetes Screen", Decimal("600.00")),
        # Metro PathLabs
        ("Metro PathLabs", "Complete Blood Count (CBC)", Decimal("400.00")),
        ("Metro PathLabs", "Lipid Profile", Decimal("850.00")),
        ("Metro PathLabs", "Liver Function Test (LFT)", Decimal("950.00")),
        ("Metro PathLabs", "HbA1c Diabetes Screen", Decimal("650.00")),
        # Suburban Health Care
        ("Suburban Health Care", "Complete Blood Count (CBC)", Decimal("320.00")),
        ("Suburban Health Care", "Lipid Profile", Decimal("750.00")),
        ("Suburban Health Care", "Liver Function Test (LFT)", Decimal("880.00")),
        ("Suburban Health Care", "HbA1c Diabetes Screen", Decimal("580.00")),
    ]

    for centre_name, test_name, price in mappings:
        centre = centres_map[centre_name]
        test = tests_map[test_name]
        stmt = select(CentreTest).where(
            CentreTest.centre_id == centre.id,
            CentreTest.test_id == test.id,
        )
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            ct = CentreTest(
                centre_id=centre.id,
                test_id=test.id,
                price=price,
                is_available=True,
            )
            db.add(ct)
            logger.info(
                "seeded_centre_test",
                centre=centre_name,
                test=test_name,
                price=str(price),
            )

    await db.commit()
    logger.info("seeding_database_completed")


async def main():
    async with AsyncSessionLocal() as session:
        await seed_database(session)


if __name__ == "__main__":
    asyncio.run(main())
