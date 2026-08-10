from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import FeedItem
from app.main import app


@pytest.mark.asyncio
async def test_get_content_feed_endpoint(mock_firestore_client: AsyncMock) -> None:
    """GET /api/v1/content/feed returns feed items with server duration_label per SPEC §9.2."""
    mock_decoded = {"uid": "test_user_feed_1", "email": "test@example.com"}

    item = FeedItem(
        id="test_user_feed_1_fx:10",
        user_id="test_user_feed_1",
        content_id="fx:10",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=2712,
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.ContentRepository.get_user_feed_count",
            AsyncMock(return_value=15),
        ),
        patch(
            "app.features.content.repository.ContentRepository.get_user_feed_items_page",
            AsyncMock(return_value=([item], None)),
        ),
        patch(
            "app.features.content.repository.ContentRepository.get_content_cache_batch",
            AsyncMock(return_value={}),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.get("/api/v1/content/feed")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["total_unconsumed"] == 15
    assert len(data["data"]["items"]) == 1
    assert data["data"]["items"][0]["duration_label"] == "45m 12s"
