import json
import uuid

import pytest
from httpx import AsyncClient

from app.core.security import compute_webhook_signature
from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


@pytest.mark.asyncio
async def test_webhook_successful_payment(
    client: AsyncClient,
    sample_booking,
):
    event_id = f"evt_{uuid.uuid4().hex}"
    provider_id = f"prov_{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }

    response = await client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["idempotent"] is False
    assert data["booking_status"] == BookingStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_webhook_failed_payment(
    client: AsyncClient,
    sample_booking,
):
    event_id = f"evt_{uuid.uuid4().hex}"
    provider_id = f"prov_{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.FAILED.value,
        "amount": str(sample_booking.amount),
    }

    response = await client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["idempotent"] is False
    assert data["booking_status"] == BookingStatus.FAILED.value


@pytest.mark.asyncio
async def test_webhook_idempotency_exact_duplicate(
    client: AsyncClient,
    sample_booking,
):
    event_id = f"evt_{uuid.uuid4().hex}"
    provider_id = f"prov_{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }

    # First attempt: processed
    res1 = await client.post("/api/v1/payments/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["idempotent"] is False
    first_payment_id = res1.json()["payment_id"]

    # Second attempt with identical payload: idempotent replay
    res2 = await client.post("/api/v1/payments/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["idempotent"] is True
    assert res2.json()["payment_id"] == first_payment_id
    assert res2.json()["booking_status"] == BookingStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_webhook_conflicting_payload_same_event_id(
    client: AsyncClient,
    sample_booking,
):
    event_id = f"evt_{uuid.uuid4().hex}"
    provider_id = f"prov_{uuid.uuid4().hex}"
    payload1 = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    # Initial success
    res1 = await client.post("/api/v1/payments/webhook", json=payload1)
    assert res1.status_code == 200

    # Same event_id but conflicting status/amount
    payload2 = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.FAILED.value,
        "amount": str(sample_booking.amount),
    }
    res2 = await client.post("/api/v1/payments/webhook", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["code"] == "EVENT_PAYLOAD_MISMATCH"


@pytest.mark.asyncio
async def test_webhook_duplicate_provider_payment_id(
    client: AsyncClient,
    sample_booking,
    regular_user,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    # Create another booking

    # First event
    provider_id = f"prov_shared_{uuid.uuid4().hex}"
    payload1 = {
        "event_id": f"evt_1_{uuid.uuid4().hex}",
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    res1 = await client.post("/api/v1/payments/webhook", json=payload1)
    assert res1.status_code == 200

    # New event with same provider_payment_id
    payload2 = {
        "event_id": f"evt_2_{uuid.uuid4().hex}",
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    res2 = await client.post("/api/v1/payments/webhook", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["code"] == "PROVIDER_PAYMENT_ID_EXISTS"


@pytest.mark.asyncio
async def test_webhook_unknown_booking(client: AsyncClient):
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_{uuid.uuid4().hex}",
        "booking_id": str(uuid.uuid4()),
        "status": PaymentStatus.SUCCESS.value,
        "amount": "100.00",
    }
    response = await client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 404
    assert response.json()["code"] == "BOOKING_NOT_FOUND"


@pytest.mark.asyncio
async def test_webhook_amount_mismatch(client: AsyncClient, sample_booking):
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_{uuid.uuid4().hex}",
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": "9999.99",  # Deliberate mismatch
    }
    response = await client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "AMOUNT_MISMATCH"


@pytest.mark.asyncio
async def test_webhook_cancelled_booking_protection(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    # 1. Cancel booking
    await client.patch(f"/api/v1/bookings/{sample_booking.id}/cancel", headers=user_headers)

    # 2. Webhook arrives attempting to confirm cancelled booking
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_{uuid.uuid4().hex}",
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    response = await client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "BOOKING_ALREADY_CANCELLED"


@pytest.mark.asyncio
async def test_webhook_hmac_signature_validation(
    client: AsyncClient,
    sample_booking,
):
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_{uuid.uuid4().hex}",
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Invalid signature header
    bad_headers = {
        "X-Webhook-Signature": "invalid-hmac-signature",
        "Content-Type": "application/json",
    }
    res_bad = await client.post("/api/v1/payments/webhook", content=body_bytes, headers=bad_headers)
    assert res_bad.status_code == 401
    assert res_bad.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"

    # Valid signature header
    valid_sig = compute_webhook_signature(body_bytes)
    good_headers = {"X-Webhook-Signature": valid_sig, "Content-Type": "application/json"}
    res_good = await client.post(
        "/api/v1/payments/webhook", content=body_bytes, headers=good_headers
    )
    assert res_good.status_code == 200
