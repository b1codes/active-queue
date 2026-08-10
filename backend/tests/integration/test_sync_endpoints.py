from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import Source
from app.main import app


@pytest.mark.asyncio
async def test_post_sources_sync_endpoint(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/sources/{source_id}/sync triggers a chunk sync and returns 200."""
    mock_decoded = {"uid": "test_user_sync_1", "email": "test@example.com"}
    source = Source(
        id="test_user_sync_1_fixture_fixture-small-playlist",
        user_id="test_user_sync_1",
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Small Playlist",
        status="active",
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.SourceRepository.get_source",
            AsyncMock(return_value=source),
        ),
        patch("app.features.content.repository.SourceRepository.update_source", AsyncMock()),
        patch(
            "app.features.content.repository.ContentRepository.upsert_content_cache_batch",
            AsyncMock(),
        ),
        patch(
            "app.features.content.repository.ContentRepository.upsert_feed_items_batch",
            AsyncMock(),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.post(
                f"/api/v1/sources/{source.id}/sync",
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["source_id"] == source.id
    assert data["data"]["items_synced"] == 15
    assert data["data"]["has_more"] is False
