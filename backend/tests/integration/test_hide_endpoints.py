from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_post_content_feed_hide_endpoint(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/content/feed/{content_id}/hide marks item consumed and returns 200."""
    mock_decoded = {"uid": "test_user_hide_1", "email": "test@example.com"}

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.ContentRepository.hide_feed_item",
            AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.post("/api/v1/content/feed/fx:123/hide")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["content_id"] == "fx:123"
    assert data["data"]["hidden"] is True
