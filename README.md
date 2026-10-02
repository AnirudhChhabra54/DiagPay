# DiagPay — Diagnostic Booking & Simulated Payment Backend

[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-53%20Passed%20(100%25)-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-75%25-brightgreen.svg)](tests/)
[![Code style](https://img.shields.io/badge/Code%20Style-Black%20%26%20Ruff-000000.svg)](https://github.com/astral-sh/ruff)

**DiagPay** is a production-oriented diagnostic healthcare appointment booking and simulated payment backend. It provides authentication, diagnostic centre and test management, centre-specific pricing, appointment bookings, simulated payments, and secure webhook processing.

---

## Verification & Execution Proofs

To allow immediate verification of the system's operational readiness, test coverage, and API surface, proofs generated from the running environment are included below:

### 1. Test Suite Proof (53/53 Tests Passing, 100% Pass Rate, 75% Overall Coverage)
Core application flows, concurrency edge cases, payment simulations, and webhook idempotency behaviors are verified through automated tests running against an async database:

![Automated Test Suite Proof](docs/images/test_results_proof.png)

### 2. Docker Health & Container Proof
The entire stack boots with health checks, automated schema migrations (`alembic upgrade head`), and data seeding in a single command:

![Docker Compose Health Proof](docs/images/docker_health_proof.png)

### 3. Interactive OpenAPI 3.0 (Swagger UI) Overview
Complete API endpoint reference (25 operations across 16 unique paths) organized by business domain with complete request/response schemas, bearer token authentication, and status codes:

![Swagger API Overview](docs/images/swagger_overview.png)

---

## Project Navigation

1. [What DiagPay Is](#1-what-diagpay-is)
2. [Why It Was Designed This Way](#2-why-it-was-designed-this-way)
3. [How to Run It](#3-how-to-run-it)
4. [What APIs Exist](#4-what-apis-exist)
5. [How the Database Is Structured](#5-how-the-database-is-structured)
6. [How Booking, Payment & Webhook Flows Work](#6-how-booking-payment--webhook-flows-work)
7. [How Edge Cases Are Handled](#7-how-edge-cases-are-handled)
8. [How the Project Is Tested](#8-how-the-project-is-tested)
9. [What Engineering Decisions Were Made](#9-what-engineering-decisions-were-made)
10. [Implementation Coverage](#10-implementation-coverage)

---

## 1. What DiagPay Is

DiagPay is a backend service for diagnostic health networks that bridges patient appointment scheduling with asynchronous payment processing:

- **Patient Experience**: Patients discover diagnostic centres, inspect available laboratory tests with centre-specific pricing, schedule appointments for future time slots, and initiate payment simulations.
- **Provider & Gateway Integration**: External payment gateways push transaction updates asynchronously via signed webhooks. DiagPay processes these events with strict deduplication, preventing duplicate state transitions.
- **Administrative Control**: Healthcare administrators manage centres, catalogued tests, availability flags, and pricing schedules with automatic cache invalidation.

---

## 2. Why It Was Designed This Way

DiagPay is built around four fundamental design principles:

### Layered Separation of Concerns
The codebase strictly decouples HTTP transport from business rules:
- **Routers (`app/api/v1/`)**: Pure controllers responsible only for HTTP parameter parsing, status codes, and invoking domain services.
- **Dependencies (`app/dependencies.py`)**: Reusable injection layer handling database sessions, JWT verification, and Role-Based Access Control (`USER` vs `ADMIN`).
- **Domain Services (`app/services/`)**: Encapsulate all business logic, validation invariants, transaction boundaries, and row-level locks.
- **Data Layer (`app/models/`)**: SQLAlchemy 2.0 type-annotated declarative models with PostgreSQL-specific constraints.

### Decoupled Healthcare Pricing (`CentreTest`)
In actual medical networks, a test like *Lipid Profile* does not have a single fixed price—cost depends on the diagnostic centre's location, equipment, and overhead. Rather than hardcoding price on the `DiagnosticTest` entity, pricing is modeled through a `CentreTest` junction table.

### Immutable Financial Snapshots
When a booking is created, the current price from `CentreTest.price` is permanently snapshotted into `Booking.amount`. If a centre updates its test rates in the future, past and pending booking amounts remain unaffected.

### Pessimistic Concurrency for Financial Safety
Financial state transitions (confirming or failing a booking) use `SELECT ... FOR UPDATE` row locks within atomic database transactions. This eliminates race conditions during simultaneous payment attempts or webhook replays.

---

## 3. How to Run It

### Option A: Docker (Recommended — Single Command)

Prerequisites: [Docker Desktop](https://www.docker.com/) installed and running.

```bash
# Clone the repository
git clone https://github.com/AnirudhChhabra54/DiagPay.git
cd DiagPay

# Start API, PostgreSQL 16, and Redis 7 in background
docker compose up --build -d
```

**What happens automatically at startup:**
1. PostgreSQL 16 and Redis 7 start with container health checks.
2. The `diagpay_api` service waits for database readiness.
3. Automatically executes database migrations (`alembic upgrade head`).
4. Automatically runs the database seeder (`python -m app.scripts.seed`).
5. Launches Uvicorn ASGI server on port `8000`.

**Verify services:**
```bash
docker compose ps
curl -s http://localhost:8000/health | python3 -m json.tool
```

To stop containers:
```bash
docker compose down
```

---

### Option B: Local Setup (Outside Docker)

Prerequisites: Python 3.12+, PostgreSQL running locally, and Redis (optional).

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Apply database migrations
alembic upgrade head

# 5. Seed initial admin & demo catalogue
python3 -m app.scripts.seed

# 6. Launch development server
uvicorn app.main:app --reload --port 8000
```

---

### Environment Configuration & Secret Labeling

Configure application variables via `.env`. A complete template is provided in `.env.example`:

| Variable | Example Value | Description |
|---|---|---|
| `PROJECT_NAME` | `DiagPay` | Application display name |
| `ENVIRONMENT` | `development` | Deployment environment (`development` / `production`) |
| `DEBUG` | `true` | Debug toggle for verbose logging and Swagger docs |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/diagpay_db` | Async SQLAlchemy PostgreSQL connection string |
| `SYNC_DATABASE_URL` | `postgresql+psycopg2://postgres:postgres@localhost:5432/diagpay_db` | Sync SQLAlchemy connection string for Alembic |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis caching and rate-limiting connection |
| `REDIS_ENABLED` | `true` | Toggle Redis caching (falls back to DB if false) |
| `JWT_SECRET_KEY` | `diagpay-super-secret-jwt-key-minimum-32-chars-for-hmac-sha256` | **Development/Demo Secret Only** — Rotate in production with secure random key |
| `JWT_ALGORITHM` | `HS256` | Symmetric signature algorithm for JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | Access token lifespan in minutes |
| `WEBHOOK_SECRET` | `diagpay-webhook-hmac-secret-key-for-verifying-payloads` | **Development/Demo Secret Only** — Rotate in production with secure random key |
| `CORS_ORIGINS` | `["http://localhost", "http://localhost:3000", "http://localhost:8000"]` | Allowed CORS origins (JSON array) |
| `RATE_LIMIT_DEFAULT` | `100/minute` | Default SlowAPI fixed-window request threshold |
| `RATE_LIMIT_AUTH` | `15/minute` | Rate limit for `/auth/login` and `/auth/signup` |
| `RATE_LIMIT_PAYMENT` | `30/minute` | Rate limit for `/payments` endpoint |
| `RATE_LIMIT_WEBHOOK` | `60/minute` | Rate limit for `/payments/webhook` endpoint |

> [!WARNING]
> The `JWT_SECRET_KEY` and `WEBHOOK_SECRET` values above are preconfigured solely for local development, demo walkthroughs, and automated test fixtures. Production deployments must inject cryptographically secure secrets via secret managers.

---

### Pre-Seeded Credentials & Demo Data

The database seeder initializes the following accounts and catalogue:

| Role | Email | Password | Permissions |
|---|---|---|---|
| **Administrator** | `admin@diagpay.com` | `AdminPass123!` | Full CRUD on centres, tests, mappings, view all bookings |
| **Regular User** | `user@diagpay.com` | `UserPass123!` | Book appointments, simulate payments, view own records |

- **3 Diagnostic Centres**: Apex Diagnostic Hub, Metro PathLabs, Suburban Health Care.
- **4 Diagnostic Tests**: Complete Blood Count (CBC), Lipid Profile, Liver Function Test (LFT), HbA1c Diabetes Screen.
- **12 Centre-Test Mappings**: Realistic individual prices per centre (e.g., CBC is ₹350.00 at Apex, ₹400.00 at Metro, ₹320.00 at Suburban).

---

## 4. What APIs Exist

Interactive documentation is available live at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Complete API Endpoint Reference

The service exposes 25 operations across 16 unique routes:

| Method | Endpoint | Access | Purpose | Key Response Codes |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | Public | Register new user account | `201`, `409`, `422` |
| `POST` | `/api/v1/auth/login` | Public | Authenticate user & issue signed JWT | `200`, `401`, `422` |
| `GET` | `/api/v1/auth/me` | Authenticated | Retrieve current user profile | `200`, `401` |
| `GET` | `/api/v1/centres` | Authenticated | List diagnostic centres (cached, paginated) | `200`, `401` |
| `GET` | `/api/v1/centres/{id}` | Authenticated | Get centre details (cached) | `200`, `404` |
| `POST` | `/api/v1/centres` | Admin | Create diagnostic centre | `201`, `403` |
| `PATCH` | `/api/v1/centres/{id}` | Admin | Update centre details & invalidate cache | `200`, `403`, `404` |
| `DELETE`| `/api/v1/centres/{id}` | Admin | Soft-deactivate centre | `200`, `403`, `404` |
| `GET` | `/api/v1/centres/{id}/tests` | Authenticated | List tests & centre-specific pricing | `200`, `404` |
| `POST` | `/api/v1/centres/{id}/tests` | Admin | Map test to centre with price | `201`, `403`, `404` |
| `PATCH` | `/api/v1/centres/{id}/tests/{tid}`| Admin | Update test price or availability flag | `200`, `403`, `404` |
| `DELETE`| `/api/v1/centres/{id}/tests/{tid}`| Admin | Unmap test from centre | `200`, `403`, `404` |
| `GET` | `/api/v1/tests` | Authenticated | List diagnostic tests (cached, paginated) | `200`, `401` |
| `GET` | `/api/v1/tests/{id}` | Authenticated | Get single test details | `200`, `404` |
| `POST` | `/api/v1/tests` | Admin | Create test in master catalogue | `201`, `403` |
| `PATCH` | `/api/v1/tests/{id}` | Admin | Update test description/name | `200`, `403`, `404` |
| `DELETE`| `/api/v1/tests/{id}` | Admin | Soft-deactivate test from catalogue | `200`, `403`, `404` |
| `POST` | `/api/v1/bookings` | Authenticated | Create diagnostic appointment (`PENDING`) | `201`, `400`, `404`, `409` |
| `GET` | `/api/v1/bookings` | Authenticated | List user bookings (admins see all) | `200`, `401` |
| `GET` | `/api/v1/bookings/{id}` | Authenticated | Get booking details (owner or admin) | `200`, `403`, `404` |
| `PATCH` | `/api/v1/bookings/{id}/cancel` | Authenticated | Cancel eligible booking (idempotent) | `200`, `403`, `404`, `409` |
| `POST` | `/api/v1/payments` | Authenticated | Simulate payment (`SUCCESS` / `FAILED`) | `201`, `403`, `404`, `409` |
| `POST` | `/api/v1/payments/webhook` | Provider | Ingest webhook event idempotently | `200`, `401`, `404`, `409` |
| `GET` | `/api/v1/health` | Public | System health endpoint under v1 prefix | `200`, `503` |
| `GET` | `/health` | Public | Readiness probe (PostgreSQL & Redis check) | `200`, `503` |

<details>
<summary><b>Click to expand verified cURL testing walkthrough</b></summary>

```bash
# 1. Login to obtain Bearer token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@diagpay.com","password":"UserPass123!"}' | jq -r .access_token)
echo "JWT Token: $TOKEN"

# 2. Browse diagnostic centres and obtain real IDs from the seeded database
CENTRE_ID=$(curl -s -X GET http://localhost:8000/api/v1/centres \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')

TEST_OFFERING=$(curl -s -X GET "http://localhost:8000/api/v1/centres/$CENTRE_ID/tests" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0]')

TEST_ID=$(echo "$TEST_OFFERING" | jq -r .test_id)
PRICE=$(echo "$TEST_OFFERING" | jq -r .price)

echo "Selected Centre: $CENTRE_ID, Test: $TEST_ID, Price: $PRICE"

# -------------------------------------------------------------
# FLOW A: In-App Simulated Payment Walkthrough
# -------------------------------------------------------------

# 3. Create appointment booking #1 (in PENDING state)
BOOKING_1=$(curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"centre_id\": \"$CENTRE_ID\",
    \"test_id\": \"$TEST_ID\",
    \"appointment_at\": \"2026-10-15T10:00:00Z\"
  }")
BOOKING_ID_1=$(echo "$BOOKING_1" | jq -r .id)
echo "Created Booking #1 (PENDING): $BOOKING_ID_1"

# 4. Simulate payment on Booking #1 (transitions PENDING -> CONFIRMED)
curl -s -X POST http://localhost:8000/api/v1/payments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"booking_id\": \"$BOOKING_ID_1\",
    \"simulate_result\": \"SUCCESS\"
  }" | jq .

# -------------------------------------------------------------
# FLOW B: External Provider Webhook Walkthrough (with HMAC Signature)
# -------------------------------------------------------------

# 5. Create a fresh appointment booking #2 (in PENDING state)
BOOKING_2=$(curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"centre_id\": \"$CENTRE_ID\",
    \"test_id\": \"$TEST_ID\",
    \"appointment_at\": \"2026-10-16T14:30:00Z\"
  }")
BOOKING_ID_2=$(echo "$BOOKING_2" | jq -r .id)
echo "Created Fresh Booking #2 (PENDING): $BOOKING_ID_2"

# 6. Construct webhook payload and compute exact HMAC-SHA256 signature
WEBHOOK_SECRET="diagpay-webhook-hmac-secret-key-for-verifying-payloads"
EVENT_ID="evt_webhook_live_001"
PAYLOAD="{\"event_id\":\"$EVENT_ID\",\"provider_payment_id\":\"pay_live_001\",\"booking_id\":\"$BOOKING_ID_2\",\"status\":\"SUCCESS\",\"amount\":\"$PRICE\"}"

SIGNATURE=$(python3 -c "import hmac, hashlib; print(hmac.new(b'$WEBHOOK_SECRET', '''$PAYLOAD'''.encode('utf-8'), hashlib.sha256).hexdigest())")
echo "Generated HMAC Signature: $SIGNATURE"

# 7. Deliver signed payment webhook to confirm Booking #2
curl -s -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -d "$PAYLOAD" | jq .

# 8. Replay identical webhook (verifying idempotent HTTP 200 response without duplicate records)
curl -s -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -d "$PAYLOAD" | jq .
```
</details>

---

## 5. How the Database Is Structured

The relational schema is enforced with PostgreSQL primary keys, foreign key constraints, and partial unique indexes:

```mermaid
erDiagram
    User ||--o{ Booking : "books"
    DiagnosticCentre ||--o{ CentreTest : "offers"
    DiagnosticTest ||--o{ CentreTest : "is offered at"
    CentreTest ||--o{ Booking : "referenced by"
    Booking ||--o{ Payment : "has transactions"

    User {
        UUID id PK
        VARCHAR email UK
        VARCHAR password_hash
        VARCHAR full_name
        VARCHAR role "USER | ADMIN"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    DiagnosticCentre {
        UUID id PK
        VARCHAR name
        VARCHAR location
        VARCHAR contact_number
        VARCHAR email
        BOOLEAN is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    DiagnosticTest {
        UUID id PK
        VARCHAR name
        VARCHAR description
        VARCHAR preparation_notes
        BOOLEAN is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    CentreTest {
        UUID id PK
        UUID centre_id FK
        UUID test_id FK
        NUMERIC price "10,2"
        BOOLEAN is_available
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Booking {
        UUID id PK
        UUID user_id FK
        UUID centre_id FK
        UUID test_id FK
        NUMERIC amount "10,2 (Snapshot)"
        VARCHAR status "PENDING|CONFIRMED|FAILED|CANCELLED"
        TIMESTAMP appointment_at
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Payment {
        UUID id PK
        UUID booking_id FK
        VARCHAR provider_payment_id
        VARCHAR event_id UK
        NUMERIC amount "10,2"
        VARCHAR status "SUCCESS|FAILED"
        VARCHAR payment_method
        JSONB raw_payload
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }
```

### Critical Database Integrity Guarantees
1. **Financial Exactness**: All monetary amounts (`CentreTest.price`, `Booking.amount`, `Payment.amount`) use `NUMERIC(10, 2)` mapped to Python `Decimal`. Floating-point arithmetic is strictly prohibited.
2. **Partial Unique Slot Index**: 
   ```sql
   CREATE UNIQUE INDEX uq_bookings_active_user_slot 
   ON bookings (user_id, centre_id, test_id, appointment_at) 
   WHERE status IN ('PENDING', 'CONFIRMED');
   ```
   Prevents double-booking the same user into the same slot while allowing re-booking if the previous booking was `CANCELLED` or `FAILED`.
3. **Compound Centre-Test Uniqueness**: `UNIQUE(centre_id, test_id)` prevents duplicate pricing definitions for the same centre-test pair.

---

## 6. How Booking, Payment & Webhook Flows Work

### Complete Lifecycle State Machine

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    participant API as FastAPI Backend
    participant Redis as Redis Cache
    participant DB as PostgreSQL (ACID)
    actor Gateway as Payment Gateway

    Note over Patient,DB: 1. Catalogue Discovery & Appointment Scheduling
    Patient->>API: GET /api/v1/centres/{id}/tests
    API->>Redis: Check Cache
    alt Cache Miss
        API->>DB: Fetch Tests & Centre-Specific Pricing
        API->>Redis: Set Key with 300s TTL
    end
    API-->>Patient: Return Test List with Pricing
    Patient->>API: POST /api/v1/bookings (centre_id, test_id, future appointment_at)
    API->>DB: Validate Centre/Test Active & Available
    API->>DB: Snapshot CentreTest.price into Booking.amount
    API->>DB: Insert Booking (status = PENDING)
    API-->>Patient: 201 Created (Booking Details)

    Note over Patient,Gateway: 2. Payment Execution & Webhook Ingestion
    alt Option A: In-App Simulated Payment
        Patient->>API: POST /api/v1/payments (booking_id, simulate_result)
        API->>DB: SELECT * FROM bookings WHERE id = :id FOR UPDATE
        API->>DB: Insert Payment Record
        API->>DB: Update Booking (CONFIRMED or FAILED)
        API-->>Patient: 201 Created (Payment & Updated Booking)
    else Option B: Asynchronous Gateway Webhook
        Gateway->>API: POST /api/v1/payments/webhook (event_id, payload, signature)
        API->>API: Verify HMAC-SHA256 Signature
        API->>DB: Check event_id in payments table
        alt Duplicate Event (Identical Payload)
            API-->>Gateway: 200 OK (idempotent: true, no duplicate write)
        else Duplicate Event (Conflicting Payload)
            API-->>Gateway: 409 Conflict (EVENT_PAYLOAD_MISMATCH)
        else New Event
            API->>DB: SELECT * FROM bookings WHERE id = :id FOR UPDATE
            API->>DB: Insert Payment & Transition Booking
            API-->>Gateway: 200 OK (Processed)
        end
    end
```

### Valid Booking State Transitions

| From State | To State | Allowed Via | Business Rationale |
|---|---|---|---|
| `PENDING` | `CONFIRMED` | Successful Payment / Webhook | Valid appointment confirmed upon payment verification. |
| `PENDING` | `FAILED` | Failed Payment / Webhook | Payment declined; slot released for rebooking. |
| `PENDING` | `CANCELLED` | User Cancellation | Patient cancels appointment before payment. |
| `CONFIRMED` | `CANCELLED` | User Cancellation | Confirmed bookings can be cancelled according to the booking rules (refund processing is outside the current simulation). |
| `CANCELLED` | `*` | *None (Terminal)* | Cancelled bookings **never** transition to `CONFIRMED` (rejected with HTTP 409). |
| `CONFIRMED` | `FAILED` | *Rejected* | Stale/out-of-order failed events will not overturn a confirmed booking. |

---

## 7. How Edge Cases Are Handled

| Edge Case | Root Problem | DiagPay Defensive Handling | Status Code |
|---|---|---|---|
| **Past Date Appointment** | Patient books an appointment in the past | Validates `appointment_at > utcnow() + 60s` at Pydantic and service level | `400 Bad Request` |
| **Concurrent Slot Collision** | Two concurrent requests attempt to book the exact same slot | Database partial unique index (`uq_bookings_active_user_slot`) enforces atomic slot collision rejection | `409 Conflict` |
| **Double Payment on Booking** | User pays twice simultaneously or retries a confirmed booking | Row lock (`with_for_update()`) serializes execution; rejects if already `CONFIRMED` | `409 Conflict` |
| **Payment on Cancelled Booking** | Payment succeeds on gateway after patient cancelled booking | State machine verifies current status under lock; refuses to confirm cancelled booking | `409 Conflict` |
| **Duplicate Webhook Replay** | Network retry re-delivers the identical payment webhook | Queries `payments.event_id`; returns immediate cached confirmation (`idempotent: true`) | `200 OK` |
| **Tampered Webhook Event** | Gateway sends existing `event_id` with modified amount or status | Payload comparator checks `amount`, `status`, `payment_id`; rejects data tampering | `409 Conflict` |
| **Invalid Webhook Signature** | Attacker spoofs payment confirmation webhook | Verifies `X-Webhook-Signature` using constant-time HMAC-SHA256 comparison | `401 Unauthorized` |
| **Redis Cache Outage** | Redis container crashes or network splits during high traffic | Cache service wraps all calls in `try/except Exception`; falls back to PostgreSQL seamlessly | `200 OK (Degraded)` |

---

## 8. How the Project Is Tested

The test suite consists of **53 automated tests** (53 passed, 0 failed, 0 skipped) covering authentication, catalogue management, centre-test pricing, bookings, payments, webhooks, concurrency scenarios, rate limiting, and health checks, with 75% overall codebase coverage:

### Test Suite Execution
```bash
# Run the entire test suite
pytest -v

# Run with line-by-line coverage
pytest --cov=app --cov-report=term-missing
```

### Test Organization
- **`tests/test_auth.py`** (6 tests): User signup, lowercase normalization, password strength, Argon2 hashing, JWT login, profile retrieval, duplicate email rejection.
- **`tests/test_centres.py`** (7 tests): Centre listing, pagination, individual centre details, admin creation, admin updates, admin soft-deletion, RBAC 403 checks.
- **`tests/test_tests.py`** (6 tests): Diagnostic test catalogue retrieval, test creation, admin authorization guards, soft deactivation.
- **`tests/test_centre_tests.py`** (7 tests): Centre-test offering retrieval, price mapping, availability toggling, unmapping.
- **`tests/test_bookings.py`** (9 tests): Appointment creation, future date validation, inactive centre/test prevention, slot collision guard, user data isolation, idempotent cancellation.
- **`tests/test_payments.py`** (5 tests): Successful payment simulation, failed payment simulation, double-confirmation prevention, cancelled booking payment guard.
- **`tests/test_webhooks.py`** (6 tests): HMAC-SHA256 signature verification, successful event ingestion, duplicate replay idempotency, payload tampering detection, cancelled booking protection.
- **`tests/test_concurrency.py`** (4 tests): Multi-threaded simultaneous booking slot collision, double payment simulation race, concurrent identical webhook delivery, state machine transition matrix.
- **`tests/test_rate_limit.py`** (1 test): SlowAPI threshold enforcement on authentication and payment endpoints.
- **`tests/test_health.py`** (2 tests): Database and cache readiness probes.

---

## 9. What Engineering Decisions Were Made

| Decision | Alternative Considered | Rationale |
|---|---|---|
| **Decoupled `CentreTest` Junction** | Flat price field on `DiagnosticTest` | Real-world diagnostic pricing varies by centre facility, operating costs, and location. |
| **Immutable Price Snapshotting** | Dynamically joining price on invoice generation | Protects financial audit trails; updating catalogue price cannot retroactively change past bookings. |
| **Pessimistic Locking (`with_for_update`)** | Optimistic locking via version column | Financial state transitions require immediate serialization without client retry loops. |
| **Argon2id Password Hashing** | Legacy `bcrypt` | Winner of the Password Hashing Competition; superior resistance against GPU and ASIC attacks. |
| **HMAC-SHA256 Webhook Verification** | Unsigned / IP-whitelisted webhooks | Verifies payload integrity and authenticity using shared-secret HMAC-SHA256 digests; rejects untrusted or tampered payloads. |
| **PostgreSQL Partial Unique Index** | Application-level `SELECT` checks | Prevents race condition slot collisions at the ACID storage engine level. |
| **Soft Deletion (`is_active = false`)** | Cascading SQL `DELETE` | Preserves referential integrity and historical records for completed patient bookings. |
| **Graceful Cache Degradation** | Hard dependency on Redis | Fault tolerance: application continues serving read traffic from PostgreSQL if Redis fails. |

---

## 10. Implementation Coverage

The following table summarizes the major capabilities implemented in DiagPay and the corresponding verification coverage:

| Capability | Implementation | Verification |
|---|---|---|
| **Authentication & Authorization** | JWT, Argon2id, RBAC (`app/api/v1/auth.py`, `app/services/auth_service.py`) | `tests/test_auth.py` |
| **Diagnostic Centres** | Centre service and CRUD APIs (`app/api/v1/centres.py`, `app/services/centre_service.py`) | `tests/test_centres.py` |
| **Diagnostic Tests** | Test catalogue and CRUD APIs (`app/api/v1/tests.py`, `app/services/test_service.py`) | `tests/test_tests.py` |
| **Centre-Test Pricing** | CentreTest mapping with centre-specific prices (`app/models/centre_test.py`, `app/api/v1/centres.py`) | `tests/test_centre_tests.py` |
| **Booking Lifecycle** | Transactional booking service (`app/api/v1/bookings.py`, `app/services/booking_service.py`) | `tests/test_bookings.py` |
| **Payment Processing** | Simulated payment service (`app/api/v1/payments.py`, `app/services/payment_service.py`) | `tests/test_payments.py` |
| **Webhook Processing** | HMAC verification + idempotency (`app/api/v1/payments.py`, `app/services/webhook_service.py`) | `tests/test_webhooks.py` |
| **Concurrency Safety** | Database constraints + row locking (`uq_bookings_active_user_slot`, `with_for_update`) | `tests/test_concurrency.py` |
| **Rate Limiting** | SlowAPI rate limiting middleware (`app/core/rate_limit.py`) | `tests/test_rate_limit.py` |
| **Health Monitoring** | Database and Redis readiness checks (`app/api/v1/health.py`) | `tests/test_health.py` |
| **Containerization** | Dockerfile and Docker Compose orchestration (`Dockerfile`, `docker-compose.yml`, `entrypoint.sh`) | Docker environment |
| **Database Versioning** | Alembic migrations (`alembic/versions/001_initial_schema.py`) | `alembic/` |

### Additional Engineering Features

The following architectural and operational capabilities are implemented and verified in the repository:
- **Redis Caching & Dynamic Invalidation**: Catalogue caching with automated pattern-based invalidation upon administrative updates (`app/services/cache_service.py`) and graceful database fallback when Redis is offline.
- **Fixed-Window Rate Limiting**: SlowAPI protection on sensitive endpoints (`/api/v1/auth/login`, `/api/v1/auth/signup`, `/api/v1/payments`, and `/api/v1/payments/webhook`) via `app/core/rate_limit.py`.
- **Structured JSON Observability**: Structured JSON logging via `structlog` (`app/logging_config.py`) with request correlation IDs (`X-Request-ID`), process latency headers (`X-Process-Time`), and automatic secret redaction.
- **Multi-Service Containerization**: Dockerfile and Docker Compose orchestration with automated health check dependencies, migrations, and seeder execution.
- **Service Readiness Probes**: Dual `/health` and `/api/v1/health` probes validating live PostgreSQL and Redis connectivity (`app/api/v1/health.py`).
- **Concurrency & Race Condition Test Suite**: Dedicated multi-threaded and asynchronous race tests validating slot collisions, payment double-spends, and replay idempotency (`tests/test_concurrency.py`).
- **HMAC Webhook Verification**: Cryptographic payload verification via HMAC-SHA256 (`app/core/security.py`).
- **Database Schema Versioning**: Automated Alembic migrations managing schema evolution (`alembic/`).

*(Note: Celery/ARQ background processing is intentionally not included because the current payment simulation does not require asynchronous job processing; all state transitions execute synchronously within ACID database transactions.)*

---

## Author

Anirudh Chhabra
