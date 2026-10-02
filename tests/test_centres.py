import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_centres(client: AsyncClient, user_headers, sample_centre):
    response = await client.get("/api/v1/centres", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(c["id"] == str(sample_centre.id) for c in data["items"])


@pytest.mark.asyncio
async def test_get_centre_by_id(client: AsyncClient, user_headers, sample_centre):
    response = await client.get(f"/api/v1/centres/{sample_centre.id}", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_centre.id)
    assert data["name"] == sample_centre.name


@pytest.mark.asyncio
async def test_get_nonexistent_centre(client: AsyncClient, user_headers):
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/centres/{fake_id}", headers=user_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "CENTRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_create_centre(client: AsyncClient, admin_headers):
    payload = {
        "name": "New Diagnostic Hub",
        "location": "500 Wellness St, Boston",
        "is_active": True,
    }
    response = await client.post("/api/v1/centres", json=payload, headers=admin_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Diagnostic Hub"
    assert data["location"] == "500 Wellness St, Boston"
    assert "id" in data


@pytest.mark.asyncio
async def test_regular_user_cannot_create_centre(client: AsyncClient, user_headers):
    payload = {
        "name": "Unauthorized Hub",
        "location": "Some Location",
    }
    response = await client.post("/api/v1/centres", json=payload, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_PRIVILEGES_REQUIRED"


@pytest.mark.asyncio
async def test_admin_update_centre(client: AsyncClient, admin_headers, sample_centre):
    payload = {"name": "Updated Apex Hub"}
    response = await client.patch(
        f"/api/v1/centres/{sample_centre.id}",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Apex Hub"


@pytest.mark.asyncio
async def test_admin_delete_centre(client: AsyncClient, admin_headers, sample_centre):
    response = await client.delete(
        f"/api/v1/centres/{sample_centre.id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
