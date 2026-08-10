from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import ContentCacheItem
from app.main import app


@pytest.mark.asyncio
async def test_post_content_match_endpoint(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/content/match matches content item to catalog and returns 200."""
    mock_decoded = {"uid": "test_user_match_1", "email": "test@example.com"}

    cache_doc = ContentCacheItem(
        content_id="fx:100",
        provider="fixture",
        external_id="100",
        title="30 Min Workout",
        duration_seconds=1800,
        published_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.ContentRepository.get_content_cache",
            AsyncMock(return_value=cache_doc),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.post(
                "/api/v1/content/match",
                json={"content_id": "fx:100"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["content_id"] == "fx:100"
    assert data["data"]["duration_seconds"] == 1800
    assert data["data"]["duration_label"] == "30m 0s"
    assert data["data"]["is_valid"] is True
    assert data["data"]["rejection_reason"] is None
    assert len(data["data"]["matching_activities"]) > 0
