import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.booking import BookingStatus


@pytest.mark.asyncio
async def test_create_booking_success(
    client: AsyncClient,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    future_time = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": future_time,
    }
    response = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == BookingStatus.PENDING.value
    assert Decimal(str(data["amount"])) == Decimal("450.00")  # Snapshot price
    assert data["centre_id"] == str(sample_centre.id)
    assert data["test_id"] == str(sample_test.id)


@pytest.mark.asyncio
async def test_create_booking_invalid_centre(
    client: AsyncClient,
    user_headers,
    sample_test,
):
    future_time = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    payload = {
        "centre_id": str(uuid.uuid4()),
        "test_id": str(sample_test.id),
        "appointment_at": future_time,
    }
    response = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "CENTRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_booking_inactive_centre(
    client: AsyncClient,
    admin_headers,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    # Deactivate centre
    await client.delete(f"/api/v1/centres/{sample_centre.id}", headers=admin_headers)

    future_time = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": future_time,
    }
    response = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "CENTRE_INACTIVE"


@pytest.mark.asyncio
async def test_create_booking_unavailable_test(
    client: AsyncClient,
    admin_headers,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    # Mark test unavailable at centre
    await client.patch(
        f"/api/v1/centres/{sample_centre.id}/tests/{sample_test.id}",
        json={"is_available": False},
        headers=admin_headers,
    )

    future_time = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": future_time,
    }
    response = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "TEST_UNAVAILABLE"


@pytest.mark.asyncio
async def test_create_booking_past_appointment(
    client: AsyncClient,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": past_time,
    }
    response = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    # Validation error caught by Pydantic validator or service logic
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_duplicate_booking(
    client: AsyncClient,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    slot = (datetime.now(UTC) + timedelta(days=4)).replace(microsecond=0).isoformat()
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": slot,
    }
    # First booking succeeds
    res1 = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert res1.status_code == 201

    # Second identical booking must conflict
    res2 = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert res2.status_code == 409
    assert res2.json()["code"] == "DUPLICATE_BOOKING"


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_booking(
    client: AsyncClient,
    other_user_headers,
    sample_booking,
):
    # other_user attempts to retrieve sample_booking (owned by regular_user)
    response = await client.get(
        f"/api/v1/bookings/{sample_booking.id}",
        headers=other_user_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACCESS"


@pytest.mark.asyncio
async def test_cancel_booking_success_and_idempotency(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    # 1. Owner cancels booking
    res1 = await client.patch(
        f"/api/v1/bookings/{sample_booking.id}/cancel",
        headers=user_headers,
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == BookingStatus.CANCELLED.value

    # 2. Repeated cancellation is idempotent
    res2 = await client.patch(
        f"/api/v1/bookings/{sample_booking.id}/cancel",
        headers=user_headers,
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == BookingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_other_user_cannot_cancel_booking(
    client: AsyncClient,
    other_user_headers,
    sample_booking,
):
    response = await client.patch(
        f"/api/v1/bookings/{sample_booking.id}/cancel",
        headers=other_user_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACCESS"
