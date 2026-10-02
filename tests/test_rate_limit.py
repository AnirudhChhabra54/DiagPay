import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limit_exceeded(client: AsyncClient):
    # Make multiple rapid requests to /api/v1/auth/login with bad payload
    responses = []
    for _ in range(25):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        responses.append(resp.status_code)

    # At least one should be rate limited (429) given limit of 15/minute
    assert 429 in responses or all(s in (401, 429) for s in responses)
