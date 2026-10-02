from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_centre_tests(
    client: AsyncClient,
    user_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    response = await client.get(
        f"/api/v1/centres/{sample_centre.id}/tests",
        headers=user_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    item = next((i for i in data if i["test_id"] == str(sample_test.id)), None)
    assert item is not None
    assert Decimal(str(item["price"])) == Decimal("450.00")
    assert item["test_name"] == sample_test.name


@pytest.mark.asyncio
async def test_admin_add_or_update_centre_test(
    client: AsyncClient,
    admin_headers,
    sample_centre,
    sample_test,
):
    payload = {
        "test_id": str(sample_test.id),
        "price": "520.50",
        "is_available": True,
    }
    response = await client.post(
        f"/api/v1/centres/{sample_centre.id}/tests",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert Decimal(str(data["price"])) == Decimal("520.50")
    assert data["is_available"] is True


@pytest.mark.asyncio
async def test_admin_update_centre_test(
    client: AsyncClient,
    admin_headers,
    sample_centre,
    sample_test,
    sample_centre_test,
):
    payload = {
        "price": "499.00",
        "is_available": False,
    }
    response = await client.patch(
        f"/api/v1/centres/{sample_centre.id}/tests/{sample_test.id}",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert Decimal(str(data["price"])) == Decimal("499.00")
    assert data["is_available"] is False


@pytest.mark.asyncio
async def test_non_admin_cannot_modify_centre_tests(
    client: AsyncClient,
    user_headers,
    sample_centre,
    sample_test,
):
    payload = {
        "test_id": str(sample_test.id),
        "price": "300.00",
    }
    response = await client.post(
        f"/api/v1/centres/{sample_centre.id}/tests",
        json=payload,
        headers=user_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_PRIVILEGES_REQUIRED"
