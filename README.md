# DiagPay — Diagnostic Booking & Simulated Payment Backend

[![Python 3.12](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**DiagPay** is a production-grade, highly available backend service engineered for diagnostic health appointment bookings and simulated financial payment transactions. Built as part of the **EVE Healthcare SDE Intern Backend Assessment**, the project emphasizes clean layered architecture, database integrity, strict concurrency control, idempotent webhook ingestion, structured observability, and comprehensive test automation.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [Architecture & System Design](#3-architecture--system-design)
4. [Tech Stack](#4-tech-stack)
5. [Folder Structure](#5-folder-structure)
6. [Database Schema & Design Detail](#6-database-schema--design-detail)
7. [API Endpoint Directory](#7-api-endpoint-directory)
8. [Core Workflows](#8-core-workflows)
   - [Authentication Flow](#authentication-flow)
   - [Booking Flow](#booking-flow)
   - [Simulated Payment Flow](#simulated-payment-flow)
   - [Webhook Idempotency Design](#webhook-idempotency-design)
9. [Edge-Case Handling & Error Responses](#9-edge-case-handling--error-responses)
10. [Environment Variables](#10-environment-variables)
11. [Quickstart: Docker Setup](#11-quickstart-docker-setup-recommended)
12. [Local Development Setup](#12-local-development-setup)
13. [Database Migrations (Alembic)](#13-database-migrations-alembic)
14. [Seeded Demo Accounts](#14-seeded-demo-accounts)
15. [Running Tests](#15-running-tests)
16. [Interactive API Documentation](#16-interactive-api-documentation)
17. [Example cURL Commands](#17-example-curl-commands)
18. [Assumptions, Design Decisions & Trade-offs](#18-assumptions-design-decisions--trade-offs)
19. [What Could Be Improved With More Time](#19-what-could-be-improved-with-more-time)

---

## 1. Project Overview

DiagPay provides the medical booking and simulated payment infrastructure for diagnostic laboratory networks. It allows patients to discover accredited diagnostic centres, inspect medical test catalogues with centre-specific pricing, schedule future appointments, and complete payments with immediate confirmation. External payment processors update booking states asynchronously through an idempotent webhook receiver.

---

## 2. Key Features

- **Robust Authentication**: Argon2 password hashing (no plaintext or hash leaks) and cryptographically signed JWT access tokens with role enforcement (`USER` vs `ADMIN`).
- **Flexible Test Pricing Model**: Real-world decoupled pricing model where diagnostic test rates are bound to specific centres (`CentreTest`), not static to the test itself.
- **Transactional Booking Lifecycle**: Validates centre and test readiness, enforces future appointment time slots, captures immutable price snapshots, and prevents duplicate active slot reservations.
- **Mock Payment Processor**: Deterministic simulation of payment attempts (`SUCCESS` / `FAILED`) updating bookings atomically without integrating live card gateways.
- **Idempotent Webhook Processing**: Guarantees zero duplicate payments, protects against out-of-order/stale events, rejects conflicting event payloads (HTTP 409), and protects cancelled bookings from accidental confirmation.
- **Redis Caching with Invalidation**: Caches high-throughput catalogue reads with automated pattern invalidation on administrative mutations, featuring graceful degradation if Redis is offline.
- **Fixed-Window Rate Limiting**: SlowAPI protection on sensitive entry points (`/auth/login`, `/auth/signup`, `/payments`, `/payments/webhook`) with automated fallback.
- **Structured JSON Logging**: Structlog integration with request correlation IDs (`X-Request-ID`), process latency headers (`X-Process-Time`), and automatic redaction of credentials and secrets.

---

## 3. Architecture & System Design

DiagPay uses a **Layered Architecture** adhering to clean code principles:

```mermaid
graph TD
    Client[Client / Third-Party Provider] -->|HTTP / REST| Middleware[CORS + Structlog Request Middleware + Rate Limiter]
    Middleware --> Routers[FastAPI Presentation Routers: /api/v1/*]
    Routers --> Dependencies[Auth & Authorization Guards: get_current_user, require_admin]
    Dependencies --> Services[Domain Services: Auth, Centre, Test, Booking, Payment, Webhook]
    Services --> DB[(PostgreSQL 16: SQLAlchemy 2.0 Async)]
    Services --> Cache[(Redis 7: Caching & Rate Limiting)]
    Services --> Security[Argon2id + PyJWT + HMAC-SHA256]
```

### Architecture Guarantees
- **Routers** are thin controllers; business logic and orchestration are strictly confined to domain services (`app/services/`).
- **Transactions** are managed explicitly with row locking (`with_for_update`) during state transitions to prevent race conditions.
- **Repository / ORM isolation**: All queries leverage SQLAlchemy 2.0 type-safe expressions with async drivers (`asyncpg`).

---

## 4. Tech Stack

- **Language**: Python 3.12+ (tested with 3.11 & 3.12)
- **Framework**: FastAPI (Async ASGI)
- **Database**: PostgreSQL 16 (with `asyncpg` async driver & `psycopg2-binary` sync driver)
- **ORM**: SQLAlchemy 2.0 (Declarative Mappings, `Mapped`, `mapped_column`)
- **Database Migrations**: Alembic
- **Validation**: Pydantic v2 & `pydantic-settings`
- **Authentication**: PyJWT (HMAC-SHA256) & `argon2-cffi` (Argon2id password hashing)
- **Caching & Rate Limiting**: Redis 7, `redis-py` (async), `slowapi`
- **Structured Logging**: `structlog` (JSON in production, colorful dev console in debug)
- **Testing**: `pytest`, `pytest-asyncio`, `httpx` (AsyncClient)
- **Containerization**: Docker & Docker Compose
- **Linting & Formatting**: Ruff & Black

---

## 5. Folder Structure

```
diagpay-backend/
├── .dockerignore
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── pyproject.toml
├── requirements.txt
├── README.md
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── config.py             # Pydantic v2 Environment Settings
│   ├── database.py           # Async and Sync SQLAlchemy 2.0 engines & sessionmakers
│   ├── dependencies.py       # Reusable Fastapi dependencies (auth, admin, DB)
│   ├── exceptions.py         # Uniform error models & global exception handlers
│   ├── logging_config.py     # Structlog structured logging & credential sanitizer
│   ├── main.py               # Application factory, middlewares & router mounts
│   ├── api/
│   │   ├── router.py         # Unified v1 router
│   │   └── v1/
│   │       ├── auth.py       # Signup, Login, Me
│   │       ├── bookings.py   # Booking creation, listing, cancel
│   │       ├── centres.py    # Centres CRUD, centre-test offerings
│   │       ├── health.py     # System readiness & service connectivity
│   │       ├── payments.py   # Simulated payments & webhook receiver
│   │       └── tests.py      # Diagnostic tests catalogue
│   ├── core/
│   │   ├── rate_limit.py     # SlowAPI limiter with Redis/memory fallback
│   │   └── security.py       # Argon2 hashing, JWT signing, HMAC-SHA256
│   ├── models/
│   │   ├── base.py           # Base, UUIDMixin, TimestampMixin
│   │   ├── booking.py        # Booking model & BookingStatus enum
│   │   ├── centre.py         # DiagnosticCentre model
│   │   ├── centre_test.py    # CentreTest mapping with price & unique constraint
│   │   ├── payment.py        # Payment model & PaymentStatus enum
│   │   ├── test.py           # DiagnosticTest model
│   │   └── user.py           # User model & UserRole enum
│   ├── schemas/
│   │   ├── booking.py        # Booking Pydantic v2 schemas
│   │   ├── centre.py         # Centre schemas
│   │   ├── centre_test.py    # Pricing mapping schemas
│   │   ├── common.py         # PaginatedResponse, MessageResponse, ErrorResponse
│   │   ├── payment.py        # Simulated payment & Webhook schemas
│   │   ├── test.py           # Test schemas
│   │   └── user.py           # Auth & User schemas
│   ├── scripts/
│   │   └── seed.py           # Idempotent database seeder (admin, centres, tests)
│   └── services/
│       ├── auth_service.py   # User registration & verification
│       ├── booking_service.py# Booking validations & transitions
│       ├── cache_service.py  # Redis cache client with graceful fallback
│       ├── centre_service.py # Centre queries & cache invalidation
│       ├── payment_service.py# Payment simulation logic
│       ├── test_service.py   # Test catalogue & mapping management
│       └── webhook_service.py# Idempotent webhook processing
├── docs/
│   ├── ARCHITECTURE.md       # Detailed technical design & state machines
│   └── IMPLEMENTATION_CHECKLIST.md # Requirement-to-file traceability matrix
└── tests/
    ├── conftest.py           # Pytest fixtures & async test database setup
    ├── test_auth.py          # Authentication tests
    ├── test_bookings.py      # Booking validations & lifecycle tests
    ├── test_centre_tests.py  # Centre-test pricing & offering tests
    ├── test_centres.py       # Diagnostic centre CRUD & authorization tests
    ├── test_health.py        # Service health endpoint tests
    ├── test_payments.py      # Simulated payment tests
    ├── test_rate_limit.py    # Rate limiter enforcement tests
    ├── test_tests.py         # Diagnostic test catalogue tests
    └── test_webhooks.py      # Webhook idempotency & concurrency tests
```

---

## 6. Database Schema & Design Detail

### Important Design Detail: Decoupled Centre-Test Pricing
A test like **Complete Blood Count (CBC)** or **Lipid Profile** has different operating expenses across different facilities. Rather than storing price as an attribute of `DiagnosticTest`, DiagPay uses a junction table `CentreTest`:

```sql
DiagnosticCentre (id, name, location, is_active)
DiagnosticTest (id, name, description, is_active)
CentreTest (id, centre_id, test_id, price, is_available) -> CONSTRAINT: UNIQUE(centre_id, test_id)
```

### Price Snapshotting in Booking
When a booking is created, the system fetches the current `CentreTest.price` and persists it directly into `Booking.amount`. This guarantees that subsequent price adjustments by laboratory administrators will never mutate the agreed transaction amount of past or pending bookings.

### Monetary Precision
All monetary quantities use SQL `NUMERIC(10, 2)` and Python `Decimal`. Floating-point values (`float`) are strictly forbidden.

---

## 7. API Endpoint Directory

All business endpoints are versioned under `/api/v1/`:

| Method | Endpoint | Access | Description | Status Codes |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | Public | Register new user account | `201`, `409`, `422` |
| `POST` | `/api/v1/auth/login` | Public | Authenticate and obtain JWT | `200`, `401`, `422` |
| `GET` | `/api/v1/auth/me` | Authenticated | Fetch current user profile | `200`, `401` |
| `GET` | `/api/v1/centres` | Authenticated | List centres (cached, paginated) | `200`, `401` |
| `GET` | `/api/v1/centres/{id}` | Authenticated | Get centre details (cached) | `200`, `404` |
| `POST` | `/api/v1/centres` | Admin | Create diagnostic centre | `201`, `403` |
| `PATCH` | `/api/v1/centres/{id}` | Admin | Update centre details | `200`, `403`, `404` |
| `DELETE`| `/api/v1/centres/{id}` | Admin | Deactivate centre (soft-delete) | `200`, `403`, `404` |
| `GET` | `/api/v1/centres/{id}/tests` | Authenticated | List tests offered at centre | `200`, `404` |
| `POST` | `/api/v1/centres/{id}/tests` | Admin | Map test to centre with price | `201`, `403`, `404` |
| `PATCH` | `/api/v1/centres/{id}/tests/{tid}` | Admin | Update test price/availability | `200`, `403`, `404` |
| `DELETE`| `/api/v1/centres/{id}/tests/{tid}` | Admin | Unmap test from centre | `200`, `403`, `404` |
| `GET` | `/api/v1/tests` | Authenticated | List tests (cached, paginated) | `200`, `401` |
| `GET` | `/api/v1/tests/{id}` | Authenticated | Get test details | `200`, `404` |
| `POST` | `/api/v1/tests` | Admin | Create test in catalog | `201`, `403` |
| `PATCH` | `/api/v1/tests/{id}` | Admin | Update catalog test | `200`, `403`, `404` |
| `DELETE`| `/api/v1/tests/{id}` | Admin | Deactivate test | `200`, `403`, `404` |
| `POST` | `/api/v1/bookings` | Authenticated | Book a diagnostic appointment | `201`, `400`, `404`, `409` |
| `GET` | `/api/v1/bookings` | Authenticated | List user's bookings (admin sees all) | `200`, `401` |
| `GET` | `/api/v1/bookings/{id}` | Authenticated | Get booking details (owner or admin) | `200`, `403`, `404` |
| `PATCH` | `/api/v1/bookings/{id}/cancel` | Authenticated | Cancel booking (idempotent) | `200`, `403`, `404`, `409` |
| `POST` | `/api/v1/payments` | Authenticated | Simulate payment (SUCCESS/FAILED) | `201`, `403`, `404`, `409` |
| `POST` | `/api/v1/payments/webhook` | Provider | Ingest payment event idempotently | `200`, `401`, `404`, `409` |
| `GET` | `/health` | Public | System readiness & dependency status | `200`, `503` |

---

## 8. Core Workflows

### Authentication Flow
1. **Signup**: Request email is trimmed and normalized to lowercase. Password is validated for minimum length (8 chars) and hashed using Argon2id. Password hashes are never serialized or returned.
2. **Login**: Verifies credentials against Argon2 hash. Issues a signed JWT bearer token containing `sub` (user UUID) and `role` (`USER` or `ADMIN`).
3. **Authorization**: Fast, stateless JWT validation via `get_current_user()` and `require_admin()` dependencies.

### Booking Flow
1. Patient selects `centre_id`, `test_id`, and `appointment_at` (must be in the future).
2. Service verifies that:
   - Centre exists and is active (`is_active = true`).
   - Test exists and is active (`is_active = true`).
   - Test is mapped and available at the centre (`is_available = true`).
   - Patient does not already have an active (`PENDING` or `CONFIRMED`) booking for the exact same test, centre, and time slot.
3. Retrieves current price snapshot from `CentreTest.price`.
4. Saves new booking in `PENDING` state inside an atomic transaction.

### Simulated Payment Flow
1. Client sends `{"booking_id": "<uuid>", "simulate_result": "SUCCESS" | "FAILED"}`.
2. Verifies booking exists and belongs to the authenticated user.
3. Rejects payment if the booking is already `CANCELLED` (HTTP 409) or `CONFIRMED` (HTTP 409).
4. Generates unique mock `provider_payment_id` (`sim_pay_*`) and `event_id` (`evt_sim_*`).
5. Atomically records payment and transitions booking state:
   - `SUCCESS` $\rightarrow$ `CONFIRMED`
   - `FAILED` $\rightarrow$ `FAILED`

### Webhook Idempotency Design
The payment webhook receiver (`POST /api/v1/payments/webhook`) supports high-concurrency ingestion and network retries:
1. **Signature Verification**: Validates `X-Webhook-Signature` using HMAC-SHA256 with constant-time equality check.
2. **Duplicate Detection**:
   - If the exact same `event_id` is re-received with identical payload attributes (`provider_payment_id`, `booking_id`, `amount`, `status`), the endpoint returns **HTTP 200 OK** (`idempotent: true`) without creating duplicate database records.
   - If an existing `event_id` is re-received with a conflicting payload, it is rejected with **HTTP 409 Conflict** (`EVENT_PAYLOAD_MISMATCH`).
3. **Row Locking**: Acquires a row lock on the target booking (`with_for_update()`) to prevent race conditions during state transitions.
4. **State Transition Rules**:
   - `CANCELLED` bookings will **never** transition to `CONFIRMED` (HTTP 409 `BOOKING_ALREADY_CANCELLED`).
   - `CONFIRMED` bookings will never transition to `FAILED` due to delayed/stale events.

---

## 9. Edge-Case Handling & Error Responses

DiagPay enforces a uniform JSON error response format:

```json
{
  "detail": "Descriptive human-readable explanation",
  "code": "SPECIFIC_ERROR_CODE"
}
```

### Standard HTTP Status Codes

- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Inactive centre/test, invalid appointment time.
- `401 Unauthorized`: Missing/invalid token, bad password, invalid webhook signature.
- `403 Forbidden`: Insufficient role permissions or accessing another user's private booking.
- `404 Not Found`: Resource with requested UUID does not exist.
- `409 Conflict`: Duplicate email, duplicate booking slot, event ID conflict, payload mismatch, or illegal state transition.
- `422 Unprocessable Content`: Validation schema failure.
- `429 Too Many Requests`: Rate limit exceeded.
- `500 Internal Server Error`: Unhandled server exception (raw database traces are never exposed).

---

## 10. Environment Variables

Configure via `.env` file (see `.env.example`):

```bash
# General
PROJECT_NAME=DiagPay
ENVIRONMENT=development
DEBUG=true
API_V1_PREFIX=/api/v1

# Databases
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/diagpay_db
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/diagpay_db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
CACHE_TTL_SECONDS=300

# Security & Secrets
JWT_SECRET_KEY=diagpay-super-secret-jwt-key-minimum-32-chars-for-hmac-sha256
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
WEBHOOK_SECRET=diagpay-webhook-hmac-secret-key-for-verifying-payloads

# CORS
CORS_ORIGINS=["http://localhost", "http://localhost:3000", "http://localhost:8000"]

# Rate Limiting
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AUTH=15/minute
RATE_LIMIT_PAYMENT=30/minute
RATE_LIMIT_WEBHOOK=60/minute
```

---

## 11. Quickstart: Docker Setup (Recommended)

Start the entire stack (FastAPI API, PostgreSQL 16, Redis 7) with a single command:

```bash
docker compose up --build -d
```

### What Happens Automatically at Startup
1. PostgreSQL and Redis initialize with health checks.
2. The `api` container waits until PostgreSQL and Redis accept connections.
3. Automatically runs database migrations: `alembic upgrade head`.
4. Automatically runs the idempotent seeder: `python -m app.scripts.seed`.
5. Starts the production Uvicorn server on port `8000`.

### Verify Docker Services
```bash
# Check container status
docker compose ps

# Check API health
curl -s http://localhost:8000/health | python3 -m json.tool

# Stream application logs
docker compose logs -f api
```

To stop all services:
```bash
docker compose down
```

---

## 12. Local Development Setup

If you prefer running outside Docker:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cp .env.example .env

# 4. Run database migrations
alembic upgrade head

# 5. Seed initial demo data
python3 -m app.scripts.seed

# 6. Start development server
uvicorn app.main:app --reload --port 8000
```

---

## 13. Database Migrations (Alembic)

Database schema versioning is managed with Alembic:

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new auto-generated migration
alembic revision --autogenerate -m "Add new field"

# Rollback one migration
alembic downgrade -1
```

---

## 14. Seeded Demo Accounts

The application seeds the following credentials upon initialization:

| Role | Email | Password | Permissions |
|---|---|---|---|
| **Administrator** | `admin@diagpay.com` | `AdminPass123!` | Full CRUD on centres, tests, mappings, view all bookings |
| **Regular User** | `user@diagpay.com` | `UserPass123!` | Create bookings, simulate payments, view own records |

### Pre-Seeded Catalog Data
- **3 Diagnostic Centres**: Apex Diagnostic Hub, Metro PathLabs, Suburban Health Care.
- **4 Diagnostic Tests**: Complete Blood Count (CBC), Lipid Profile, Liver Function Test (LFT), HbA1c Diabetes Screen.
- **12 Centre-Test Mappings**: Realistic individual prices per centre (e.g. CBC is ₹350 at Apex, ₹400 at Metro, ₹320 at Suburban).

---

## 15. Running Tests

The test suite runs with in-memory SQLite and mock cache, requiring zero external services:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full pytest suite with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing
```

### Test Suite Structure (53 Tests Passing)
- `tests/test_auth.py`: User registration, duplicate detection, password hashing, JWT login, profile retrieval.
- `tests/test_centres.py`: Pagination, centre retrieval, admin creation/updates, non-admin rejection.
- `tests/test_tests.py`: Catalogue listing, test creation, admin authorization.
- `tests/test_centre_tests.py`: Dynamic pricing assignment, availability toggling.
- `tests/test_bookings.py`: Booking creation, past date rejection, duplicate slot guard, user access isolation, idempotent cancellation.
- `tests/test_payments.py`: Successful/failed payment simulation, double confirmation rejection, cancelled booking guards.
- `tests/test_webhooks.py`: Ingestion, duplicate replay idempotency, conflicting payload detection, cancelled booking protection, HMAC verification.
- `tests/test_concurrency.py`: Partial unique slot collision, payment double confirmation, concurrent identical webhooks, and state machine matrix.
- `tests/test_rate_limit.py`: Rapid request threshold enforcement.
- `tests/test_health.py`: System readiness and dependency validation.

---

## 16. Interactive API Documentation

Once the server is running, explore the interactive OpenAPI documentation:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 17. Example cURL Commands

### 1. User Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@diagpay.com",
    "password": "UserPass123!"
  }'
```

### 2. Discover Diagnostic Centres
```bash
curl -X GET http://localhost:8000/api/v1/centres?page=1&page_size=10 \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

### 3. Retrieve Tests Offered at a Diagnostic Centre
```bash
curl -X GET http://localhost:8000/api/v1/centres/<CENTRE_ID>/tests \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

### 4. Create a Diagnostic Booking
```bash
curl -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "centre_id": "<CENTRE_ID>",
    "test_id": "<TEST_ID>",
    "appointment_at": "2026-10-15T10:00:00Z"
  }'
```

### 5. Simulate Payment
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": "<BOOKING_ID>",
    "simulate_result": "SUCCESS"
  }'
```

### 6. Process Payment Provider Webhook
```bash
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_live_9981",
    "provider_payment_id": "pay_live_4421",
    "booking_id": "<BOOKING_ID>",
    "status": "SUCCESS",
    "amount": "350.00"
  }'
```

### 7. Replay Identical Webhook (Idempotent Test)
```bash
# Re-sending the identical payload returns HTTP 200 with "idempotent": true
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_live_9981",
    "provider_payment_id": "pay_live_4421",
    "booking_id": "<BOOKING_ID>",
    "status": "SUCCESS",
    "amount": "350.00"
  }'
```

---

## 18. Assumptions, Design Decisions & Trade-offs

1. **Independent Pricing Model**: Decoupling tests from centres mirrors real-world healthcare marketplaces where laboratory pricing varies by geographical location and facility equipment.
2. **Soft Deletions**: Deactivating diagnostic centres or tests sets `is_active = false` rather than issuing cascading SQL `DELETE`s. This guarantees historical audit trails and patient booking receipts remain intact.
3. **Pessimistic Row Locking over Optimistic Locking**: For financial transitions on bookings, `SELECT ... FOR UPDATE` was chosen over version columns because payment attempts for an individual booking are low frequency but carry high consistency risks (double spend, duplicate confirmation).
4. **Synchronous vs Asynchronous Webhooks**: Webhook ingestion performs idempotency checks and booking transitions synchronously within a single database transaction. For very high webhook throughput (>10,000 req/sec), a Kafka or RabbitMQ queue would decouple receipt from execution. For this service's scope, transactional synchronous processing guarantees zero lag between provider update and user confirmation.
5. **Argon2id vs Bcrypt**: Argon2id was selected for password hashing due to superior resistance against GPU/ASIC-assisted brute-force attacks compared to legacy bcrypt.

---

## 19. What Could Be Improved With More Time

1. **Asynchronous Task Queue (Celery / ARQ)**: Offloading webhook side-effects (e.g. sending SMS or Email booking confirmations) to background workers.
2. **Audit Log Table**: Maintaining an immutable change log table tracking every state transition with timestamp, actor, previous status, and new status.
3. **Multi-Tenancy Support**: Partitioning centres into healthcare networks / hospital chains with dedicated tenant administrators.
4. **Time Slot Capacity Limits**: Enforcing maximum concurrent appointments per hour per centre room.
5. **Automated Refresh Tokens**: Implementing rotating refresh tokens stored securely in HTTP-only cookies.
