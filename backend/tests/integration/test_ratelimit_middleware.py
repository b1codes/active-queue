from __future__ import annotations

from unittest.mock import patch

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
