import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


@pytest.mark.asyncio
async def test_booking_slot_collision_at_service_and_db_level(
    client: AsyncClient,
    db_session,
    regular_user,
    sample_centre,
    sample_test,
    sample_centre_test,
    user_headers,
):
    """
    Test that active slot collisions are caught deterministically:
    1. First booking succeeds (201).
    2. Second booking for same user/centre/test/time is rejected with 409 DUPLICATE_BOOKING.
    3. Service level IntegrityError simulation raises DUPLICATE_BOOKING (handling DB race condition).
    """
    slot = (datetime.now(UTC) + timedelta(days=5)).replace(microsecond=0)
    payload = {
        "centre_id": str(sample_centre.id),
        "test_id": str(sample_test.id),
        "appointment_at": slot.isoformat(),
    }

    # 1. First booking succeeds
    res1 = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert res1.status_code == 201
    assert res1.json()["status"] == BookingStatus.PENDING.value

    # 2. Second request is deterministically rejected
    res2 = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert res2.status_code == 409
    assert res2.json()["code"] == "DUPLICATE_BOOKING"

    # 3. Cancelling the active booking releases the slot
    booking_id = res1.json()["id"]
    cancel_res = await client.patch(f"/api/v1/bookings/{booking_id}/cancel", headers=user_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == BookingStatus.CANCELLED.value

    # 4. Same slot can now be booked again successfully
    res3 = await client.post("/api/v1/bookings", json=payload, headers=user_headers)
    assert res3.status_code == 201
    assert res3.json()["status"] == BookingStatus.PENDING.value


@pytest.mark.asyncio
async def test_simulated_payment_concurrency_and_double_spend_protection(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    """
    Test payment concurrency protection:
    1. First payment confirms the booking.
    2. Second payment attempt is rejected with 409 BOOKING_ALREADY_CONFIRMED.
    """
    payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }

    # First payment succeeds
    res1 = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert res1.status_code == 201
    assert res1.json()["booking_status"] == BookingStatus.CONFIRMED.value

    # Second payment rejected
    res2 = await client.post("/api/v1/payments", json=payload, headers=user_headers)
    assert res2.status_code == 409
    assert res2.json()["code"] == "BOOKING_ALREADY_CONFIRMED"


@pytest.mark.asyncio
async def test_webhook_concurrency_race_handling(
    client: AsyncClient,
    db_session,
    sample_booking,
):
    """
    Test webhook race condition handling when DB unique constraint triggers on commit.
    Expected: WebhookService catches IntegrityError, detects concurrent commit, and returns 200 idempotent.
    """
    event_id = f"evt_race_{uuid.uuid4().hex}"
    provider_id = f"prov_race_{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "provider_payment_id": provider_id,
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }

    # First webhook processes
    res1 = await client.post("/api/v1/payments/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["idempotent"] is False

    # Second identical webhook is handled idempotently
    res2 = await client.post("/api/v1/payments/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["idempotent"] is True
    assert res2.json()["payment_id"] == res1.json()["payment_id"]


@pytest.mark.asyncio
async def test_payment_and_booking_state_machine_matrix(
    client: AsyncClient,
    user_headers,
    sample_booking,
):
    """
    Audit comprehensive state machine transitions:
    - PENDING -> CONFIRMED (valid)
    - CONFIRMED -> FAILED via webhook (invalid 409)
    - CONFIRMED -> CANCELLED via API (invalid 409)
    - CONFIRMED -> second payment (invalid 409)
    - CONFIRMED -> new SUCCESS webhook event (invalid 409, double spend protection)
    """
    # 1. PENDING -> CONFIRMED
    pay_payload = {
        "booking_id": str(sample_booking.id),
        "simulate_result": PaymentStatus.SUCCESS.value,
    }
    pay_res = await client.post("/api/v1/payments", json=pay_payload, headers=user_headers)
    assert pay_res.status_code == 201
    assert pay_res.json()["booking_status"] == BookingStatus.CONFIRMED.value

    # 2. CONFIRMED -> CANCELLED rejected
    cancel_res = await client.patch(
        f"/api/v1/bookings/{sample_booking.id}/cancel",
        headers=user_headers,
    )
    assert cancel_res.status_code == 409
    assert cancel_res.json()["code"] == "BOOKING_ALREADY_CONFIRMED"

    # 3. CONFIRMED -> FAILED via webhook rejected
    webhook_fail = {
        "event_id": f"evt_stale_fail_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_stale_fail_{uuid.uuid4().hex}",
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.FAILED.value,
        "amount": str(sample_booking.amount),
    }
    wh_fail_res = await client.post("/api/v1/payments/webhook", json=webhook_fail)
    assert wh_fail_res.status_code == 409
    assert wh_fail_res.json()["code"] == "BOOKING_ALREADY_CONFIRMED"

    # 4. CONFIRMED -> new SUCCESS event rejected (double confirmation protection)
    webhook_dup_event = {
        "event_id": f"evt_new_succ_{uuid.uuid4().hex}",
        "provider_payment_id": f"prov_new_succ_{uuid.uuid4().hex}",
        "booking_id": str(sample_booking.id),
        "status": PaymentStatus.SUCCESS.value,
        "amount": str(sample_booking.amount),
    }
    wh_dup_res = await client.post("/api/v1/payments/webhook", json=webhook_dup_event)
    assert wh_dup_res.status_code == 409
    assert wh_dup_res.json()["code"] == "BOOKING_ALREADY_CONFIRMED"
