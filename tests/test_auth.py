import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    payload = {
        "email": "NEW_USER@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new_user@example.com"  # Lowercase normalized
    assert data["full_name"] == "Test User"
    assert data["role"] == "USER"
    assert "password" not in data
    assert "password_hash" not in data
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, regular_user):
    payload = {
        "email": regular_user.email,  # user@diagpay.com
        "password": "AnotherPassword123!",
        "full_name": "Duplicate User",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, regular_user):
    payload = {
        "email": "USER@diagpay.com",  # Should normalize
        "password": "UserPass123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "user@diagpay.com"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, regular_user):
    # Wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user.email, "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

    # Non-existent user
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "SomePassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_get_me_authorized(client: AsyncClient, user_headers):
    response = await client.get("/api/v1/auth/me", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@diagpay.com"
    assert data["role"] == "USER"
