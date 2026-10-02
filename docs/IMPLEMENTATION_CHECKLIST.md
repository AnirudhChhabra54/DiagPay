# DiagPay — Implementation Verification Checklist

This document maps every requirement from the EVE Healthcare SDE Intern Backend Assignment to its corresponding implementation files, API endpoints, database models, and automated tests.

---

## 1. Authentication & Security

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| User Signup (email lowercase, duplicate rejection, Argon2 hash) | `app/services/auth_service.py`<br>`app/schemas/user.py` | `POST /api/v1/auth/signup` (201 Created) | `tests/test_auth.py::test_signup_success`<br>`tests/test_auth.py::test_signup_duplicate_email` | Verified |
| User Login (verify credentials, return JWT access token) | `app/services/auth_service.py`<br>`app/core/security.py` | `POST /api/v1/auth/login` (200 OK) | `tests/test_auth.py::test_login_success`<br>`tests/test_auth.py::test_login_invalid_credentials` | Verified |
| Current User Profile (`/auth/me`) | `app/api/v1/auth.py`<br>`app/dependencies.py` | `GET /api/v1/auth/me` (200 OK) | `tests/test_auth.py::test_get_me_authorized`<br>`tests/test_auth.py::test_get_me_unauthorized` | Verified |
| JWT Authentication & Dependencies | `app/core/security.py`<br>`app/dependencies.py` | `get_current_user()`<br>`require_admin()` | `tests/test_auth.py::test_get_me_unauthorized`<br>`tests/test_centres.py::test_regular_user_cannot_create_centre` | Verified |
| Argon2 Password Hashing | `app/core/security.py` | `hash_password()`<br>`verify_password()` | `tests/test_auth.py` | Verified |
| No Password Leakage | `app/schemas/user.py`<br>`app/logging_config.py` | Redacted in schemas & logs | `tests/test_auth.py::test_signup_success` | Verified |

---

## 2. Diagnostic Centres & Tests

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| List Centres (paginated, cached) | `app/services/centre_service.py`<br>`app/api/v1/centres.py` | `GET /api/v1/centres` (200 OK) | `tests/test_centres.py::test_list_centres` | Verified |
| Get Centre by ID | `app/services/centre_service.py` | `GET /api/v1/centres/{centre_id}` (200 OK) | `tests/test_centres.py::test_get_centre_by_id`<br>`tests/test_centres.py::test_get_nonexistent_centre` | Verified |
| Admin Create Centre | `app/services/centre_service.py` | `POST /api/v1/centres` (201 Created) | `tests/test_centres.py::test_admin_create_centre`<br>`tests/test_centres.py::test_regular_user_cannot_create_centre` | Verified |
| Admin Update Centre | `app/services/centre_service.py` | `PATCH /api/v1/centres/{centre_id}` (200 OK) | `tests/test_centres.py::test_admin_update_centre` | Verified |
| Admin Deactivate Centre | `app/services/centre_service.py` | `DELETE /api/v1/centres/{centre_id}` (200 OK) | `tests/test_centres.py::test_admin_delete_centre` | Verified |
| List Tests (paginated, cached) | `app/services/test_service.py`<br>`app/api/v1/tests.py` | `GET /api/v1/tests` (200 OK) | `tests/test_tests.py::test_list_tests` | Verified |
| Get Test by ID | `app/services/test_service.py` | `GET /api/v1/tests/{test_id}` (200 OK) | `tests/test_tests.py::test_get_test_by_id` | Verified |
| Admin Create Test | `app/services/test_service.py` | `POST /api/v1/tests` (201 Created) | `tests/test_tests.py::test_admin_create_test`<br>`tests/test_tests.py::test_non_admin_cannot_create_test` | Verified |
| Admin Update Test | `app/services/test_service.py` | `PATCH /api/v1/tests/{test_id}` (200 OK) | `tests/test_tests.py::test_admin_update_test` | Verified |
| Admin Deactivate Test | `app/services/test_service.py` | `DELETE /api/v1/tests/{test_id}` (200 OK) | `tests/test_tests.py::test_admin_delete_test` | Verified |

---

## 3. Centre-Test Pricing & Offerings

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| Centre-Specific Pricing Mapping (`CentreTest`) | `app/models/centre_test.py`<br>`uq_centre_test` constraint | `POST /api/v1/centres/{id}/tests`<br>`GET /api/v1/centres/{id}/tests` | `tests/test_centre_tests.py::test_list_centre_tests`<br>`tests/test_centre_tests.py::test_admin_add_or_update_centre_test` | Verified |
| List Offered Tests at Centre | `app/services/centre_service.py` | `GET /api/v1/centres/{centre_id}/tests` | `tests/test_centre_tests.py::test_list_centre_tests` | Verified |
| Update Test Availability / Price | `app/services/test_service.py` | `PATCH /api/v1/centres/{id}/tests/{test_id}` | `tests/test_centre_tests.py::test_admin_update_centre_test` | Verified |
| Enforce Decimal / Monetary Correctness | `app/models/centre_test.py` (`Numeric(10, 2)`) | Schema validation | `tests/test_centre_tests.py` | Verified |

---

## 4. Booking System

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| Authenticated Booking Creation | `app/services/booking_service.py` | `POST /api/v1/bookings` (201 Created) | `tests/test_bookings.py::test_create_booking_success` | Verified |
| Validate Centre Exists & Active | `app/services/booking_service.py` | `CENTRE_NOT_FOUND`, `CENTRE_INACTIVE` | `tests/test_bookings.py::test_create_booking_invalid_centre`<br>`tests/test_bookings.py::test_create_booking_inactive_centre` | Verified |
| Validate Test Exists & Available at Centre | `app/services/booking_service.py` | `TEST_NOT_FOUND`, `TEST_UNAVAILABLE` | `tests/test_bookings.py::test_create_booking_unavailable_test` | Verified |
| Future Appointment Validation | `app/schemas/booking.py`<br>`app/services/booking_service.py` | `INVALID_APPOINTMENT_TIME` | `tests/test_bookings.py::test_create_booking_past_appointment` | Verified |
| Price Snapshot from `CentreTest.price` | `app/services/booking_service.py` | `booking.amount = mapping.price` | `tests/test_bookings.py::test_create_booking_success` | Verified |
| Initial State = `PENDING` | `app/models/booking.py` | `BookingStatus.PENDING` | `tests/test_bookings.py::test_create_booking_success` | Verified |
| Prevent Duplicate Active Bookings | `app/models/booking.py`<br>`uq_bookings_active_user_slot` | `DUPLICATE_BOOKING` (409 Conflict) via partial unique index `status IN ('PENDING', 'CONFIRMED')` | `tests/test_bookings.py::test_create_duplicate_booking`<br>`tests/test_concurrency.py::test_booking_slot_collision_at_service_and_db_level` | Verified |
| User Data Access Isolation | `app/services/booking_service.py` | `GET /api/v1/bookings`<br>`GET /api/v1/bookings/{id}` | `tests/test_bookings.py::test_user_cannot_access_another_users_booking` | Verified |
| Booking Cancellation | `app/services/booking_service.py` | `PATCH /api/v1/bookings/{id}/cancel` | `tests/test_bookings.py::test_cancel_booking_success_and_idempotency` | Verified |
| Cancellation Idempotency | `app/services/booking_service.py` | Returns existing CANCELLED state | `tests/test_bookings.py::test_cancel_booking_success_and_idempotency` | Verified |
| Disallow Other User Cancellation | `app/services/booking_service.py` | `FORBIDDEN_ACCESS` (403 Forbidden) | `tests/test_bookings.py::test_other_user_cannot_cancel_booking` | Verified |

---

## 5. Simulated Payment Service

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| Simulated Payment Processing | `app/services/payment_service.py` | `POST /api/v1/payments` (201 Created) | `tests/test_payments.py::test_simulated_payment_success`<br>`tests/test_payments.py::test_simulated_payment_failure` | Verified |
| Authenticate User & Validate Ownership | `app/services/payment_service.py` | `FORBIDDEN_ACCESS` (403 Forbidden) | `tests/test_payments.py::test_simulated_payment_forbidden_for_other_user` | Verified |
| Reject Cancelled Booking | `app/services/payment_service.py` | `BOOKING_ALREADY_CANCELLED` (409 Conflict) | `tests/test_payments.py::test_simulated_payment_cancelled_booking_rejected` | Verified |
| Reject Already Confirmed Booking | `app/services/payment_service.py` | `BOOKING_ALREADY_CONFIRMED` (409 Conflict) | `tests/test_payments.py::test_simulated_payment_already_confirmed_rejected` | Verified |
| Atomic Booking Status Transition | `app/services/payment_service.py` | `PENDING -> CONFIRMED` (SUCCESS)<br>`PENDING -> FAILED` (FAILED) | `tests/test_payments.py::test_simulated_payment_success`<br>`tests/test_payments.py::test_simulated_payment_failure` | Verified |
| Unique Payment IDs | `app/models/payment.py` | `provider_payment_id`, `event_id` | `tests/test_payments.py::test_simulated_payment_success` | Verified |

---

## 6. Payment Webhook & Idempotency

| Requirement | Implementation File(s) | Endpoint / Component | Automated Test(s) | Status |
|---|---|---|---|---|
| Webhook Endpoint | `app/api/v1/payments.py` | `POST /api/v1/payments/webhook` (200 OK) | `tests/test_webhooks.py::test_webhook_successful_payment` | Verified |
| Event ID Uniqueness | `app/models/payment.py` | `uq_payment_event_id` constraint | `tests/test_webhooks.py::test_webhook_idempotency_exact_duplicate` | Verified |
| Idempotent Duplicate Processing | `app/services/webhook_service.py` | Returns 200 OK + `idempotent: true`, no new DB records | `tests/test_webhooks.py::test_webhook_idempotency_exact_duplicate` | Verified |
| Conflicting Duplicate Event Rejection | `app/services/webhook_service.py` | `EVENT_PAYLOAD_MISMATCH` (409 Conflict) | `tests/test_webhooks.py::test_webhook_conflicting_payload_same_event_id` | Verified |
| Duplicate Provider Payment ID Rejection | `app/services/webhook_service.py` | `PROVIDER_PAYMENT_ID_EXISTS` (409 Conflict) | `tests/test_webhooks.py::test_webhook_duplicate_provider_payment_id` | Verified |
| Unknown Booking Handling | `app/services/webhook_service.py` | `BOOKING_NOT_FOUND` (404 Not Found) | `tests/test_webhooks.py::test_webhook_unknown_booking` | Verified |
| Amount Mismatch Detection | `app/services/webhook_service.py` | `AMOUNT_MISMATCH` (409 Conflict) | `tests/test_webhooks.py::test_webhook_amount_mismatch` | Verified |
| Cancelled Booking Protection | `app/services/webhook_service.py` | Never move `CANCELLED` to `CONFIRMED` | `tests/test_webhooks.py::test_webhook_cancelled_booking_protection` | Verified |
| Stale State Transition Protection | `app/services/webhook_service.py` | Never move `CONFIRMED` to `FAILED` | `tests/test_webhooks.py` | Verified |
| Row Locking & Concurrency Protection | `app/services/webhook_service.py` | `select(Booking).with_for_update()` | `tests/test_webhooks.py` | Verified |
| HMAC Signature Verification | `app/core/security.py`<br>`app/dependencies.py` | Header `X-Webhook-Signature` | `tests/test_webhooks.py::test_webhook_hmac_signature_validation` | Verified |

---

## 7. Bonus Implementations & Infrastructure

| Feature | Implementation File(s) | Verification Command / Metric | Status |
|---|---|---|---|
| Redis Caching & Invalidation | `app/services/cache_service.py` | Graceful degradation if Redis unavailable | Verified |
| Fixed-Window Rate Limiting | `app/core/rate_limit.py` | SlowAPI limiter on auth, payments, webhooks | Verified (`test_rate_limit_exceeded`) |
| Structured Logging with Structlog | `app/logging_config.py`<br>`app/main.py` | Correlation IDs, timing, sensitive data redaction | Verified |
| Docker & Docker Compose | `Dockerfile`<br>`docker-compose.yml`<br>`entrypoint.sh` | Multi-container setup (API, Postgres, Redis) with healthchecks | Verified |
| Alembic Migrations | `alembic/versions/001_initial_schema.py`<br>`alembic.ini` | `alembic upgrade head` | Verified |
| Idempotent Seed Data | `app/scripts/seed.py` | Seeds Admin, User, 3 Centres, 4 Tests, 12 Mappings | Verified |
| Service Health Check | `app/api/v1/health.py` | `GET /health` returns DB and Redis status | Verified (`test_health_check`) |
| Automated Pytest Suite | `tests/` | 53 unit, integration, and concurrency tests passing | Verified |
| Linting & Formatting | `pyproject.toml` | Ruff 0 errors, Black clean | Verified |
