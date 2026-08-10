from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_post_sources_success(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/sources creates a source document and returns 201."""
    mock_decoded = {"uid": "test_user_sources_1", "email": "test@example.com"}

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.content.repository.SourceRepository.get_user_sources",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.features.content.repository.SourceRepository.get_user_source_by_external_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.features.content.repository.SourceRepository.create_source",
            AsyncMock(side_effect=lambda s: s),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.post(
                "/api/v1/sources",
                json={"url_or_id": "fixture-small-playlist"},
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["external_source_id"] == "fixture-small-playlist"
    assert data["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_post_sources_watch_later_rejection(mock_firestore_client: AsyncMock) -> None:
    """POST /api/v1/sources rejects Watch Later (WL) with 422 SOURCE_UNSUPPORTED per SPEC §9.3."""
    mock_decoded = {"uid": "test_user_sources_2", "email": "test@example.com"}

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            resp = await client.post(
                "/api/v1/sources",
                json={"url_or_id": "WL"},
            )

    assert resp.status_code == 422
    data = resp.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "SOURCE_UNSUPPORTED"
    assert "restricted by YouTube API" in data["error"]["message"]
