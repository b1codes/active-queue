from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_rate_limit_headers_emitted() -> None:
    """API responses contain X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers."""
    mock_decoded = {"uid": "test_user_rl_1", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.get("/api/v1/activities")

    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers
    assert resp.headers["X-RateLimit-Limit"] == "60"


@pytest.mark.asyncio
async def test_health_endpoint_bypasses_rate_limit(mock_firestore_client: MagicMock) -> None:
    """GET /healthz bypasses rate limiting."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429() -> None:
    """Exceeding request limit returns HTTP 429, RATE_LIMITED envelope, and Retry-After header."""
    mock_decoded = {"uid": "test_user_exceed_429", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-429-token"},
        ) as client:
            # Send 60 allowed requests
            for _ in range(60):
                resp = await client.get("/api/v1/activities")
                assert resp.status_code == 200

            # 61st request triggers rate limit
            resp_exceeded = await client.get("/api/v1/activities")
            assert resp_exceeded.status_code == 429
            assert "Retry-After" in resp_exceeded.headers
            assert resp_exceeded.headers["X-RateLimit-Remaining"] == "0"
            json_body = resp_exceeded.json()
            assert json_body["status"] == "error"
            assert json_body["error"]["code"] == "RATE_LIMITED"
            assert "Rate limit of 60 requests per minute exceeded" in json_body["error"]["message"]
