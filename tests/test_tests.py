import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tests(client: AsyncClient, user_headers, sample_test):
    response = await client.get("/api/v1/tests", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1
    assert any(t["id"] == str(sample_test.id) for t in data["items"])


@pytest.mark.asyncio
async def test_get_test_by_id(client: AsyncClient, user_headers, sample_test):
    response = await client.get(f"/api/v1/tests/{sample_test.id}", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_test.id)
    assert data["name"] == sample_test.name


@pytest.mark.asyncio
async def test_admin_create_test(client: AsyncClient, admin_headers):
    payload = {
        "name": "Thyroid Stimulating Hormone (TSH)",
        "description": "Screen for thyroid disorders",
        "is_active": True,
    }
    response = await client.post("/api/v1/tests", json=payload, headers=admin_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Thyroid Stimulating Hormone (TSH)"
    assert "id" in data


@pytest.mark.asyncio
async def test_non_admin_cannot_create_test(client: AsyncClient, user_headers):
    payload = {"name": "Unauthorized Test"}
    response = await client.post("/api/v1/tests", json=payload, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_PRIVILEGES_REQUIRED"


@pytest.mark.asyncio
async def test_admin_update_test(client: AsyncClient, admin_headers, sample_test):
    payload = {"description": "Updated detailed hematology blood panel"}
    response = await client.patch(
        f"/api/v1/tests/{sample_test.id}",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated detailed hematology blood panel"


@pytest.mark.asyncio
async def test_admin_delete_test(client: AsyncClient, admin_headers, sample_test):
    response = await client.delete(
        f"/api/v1/tests/{sample_test.id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
