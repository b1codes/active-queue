from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import FeedItem
from app.main import app


@pytest.mark.asyncio
async def test_post_content_match_time_endpoint(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/content/match-time matches target time block to feed candidates and returns 200."""
    mock_decoded = {"uid": "test_user_tm_1", "email": "test@example.com"}

    item = FeedItem(
        id="test_user_tm_1_fx:20",
        user_id="test_user_tm_1",
        content_id="fx:20",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=1830,
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.ContentRepository.get_all_unconsumed_feed_items",
            AsyncMock(return_value=[item]),
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
            resp = await client.post(
                "/api/v1/content/match-time",
                json={"target_duration_seconds": 1800},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["target_duration_seconds"] == 1800
    assert data["data"]["target_duration_label"] == "30m 0s"
    assert data["data"]["is_valid"] is True
    assert data["data"]["window_type"] == "primary"
    assert data["data"]["rejection_reason"] is None
    assert len(data["data"]["matched_items"]) == 1
    assert data["data"]["matched_items"][0]["duration_seconds"] == 1830
