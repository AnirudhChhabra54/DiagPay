import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


@pytest.mark.asyncio
async def test_simulated_payment_success(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    response = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == PaymentStatus.SUCCESS.value
    assert data["booking_status"] == BookingStatus.CONFIRMED.value
    assert Decimal(str(data["amount"])) == sample_booking.amount
    assert "provider_payment_id" in data
    assert "event_id" in data


@pytest.mark.asyncio
async def test_simulated_payment_failure(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.FAILED.value,
    }
    response = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == PaymentStatus.FAILED.value
    assert data["booking_status"] == BookingStatus.FAILED.value


@pytest.mark.asyncio
async def test_simulated_payment_invalid_booking(
    client: AsyncClient,
    user_headers,
):
    payload = {
        "booking_id": str(uuid.uuid4()),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    response = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "BOOKING_NOT_FOUND"


@pytest.mark.asyncio
async def test_simulated_payment_forbidden_for_other_user(
    client: AsyncClient,
    other_user_headers,
    sample_booking,
):
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    response = await client.post("/api/v1/payments", json=payload, headers=other_user_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACCESS"


@pytest.mark.asyncio
async def test_simulated_payment_cancelled_booking_rejected(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    # Cancel first
    await client.patch(f"/api/v1/bookings/{sample_booking.id}/cancel", headers=user_headers)

    # Attempt to pay
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    response = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "BOOKING_ALREADY_CANCELLED"


@pytest.mark.asyncio
async def test_simulated_payment_already_confirmed_rejected(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    # First payment succeeds
    res1 = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert res1.status_code == 201

    # Second payment attempt must be rejected
    res2 = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert res2.status_code == 409
    assert res2.json()["code"] == "BOOKING_ALREADY_CONFIRMED"
