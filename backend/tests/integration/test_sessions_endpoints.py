from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import ContentCacheItem
from app.features.sessions.models import Session
from app.main import app


@pytest.mark.asyncio
async def test_create_start_and_complete_session_endpoints(
    mock_firestore_client: AsyncMock,
) -> None:
    """POST /api/v1/sessions, POST /api/v1/sessions/{id}/start, and POST /api/v1/sessions/{id}/complete lifecycle per SPEC §9.5-9.6."""
    mock_decoded = {"uid": "test_user_sess_1", "email": "test@example.com"}

    cache_doc = ContentCacheItem(
        content_id="fx:50",
        provider="fixture",
        external_id="50",
        title="Running Video",
        duration_seconds=1800,
        published_at=datetime.now(UTC),
    )

    pending_session = Session(
        id="s_test_123",
        user_id="test_user_sess_1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:50",
        duration_seconds=1800,
        status="pending",
    )

    completed_session = Session(
        id="s_test_123",
        user_id="test_user_sess_1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:50",
        duration_seconds=1800,
        status="completed",
        completed_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.sessions.repository.SessionRepository.get_active_user_session",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.features.content.repository.ContentRepository.get_content_cache",
            AsyncMock(return_value=cache_doc),
        ),
        patch(
            "app.features.sessions.repository.SessionRepository.create_session",
            AsyncMock(side_effect=lambda s: s),
        ),
        patch(
            "app.features.sessions.repository.SessionRepository.get_session",
            AsyncMock(return_value=pending_session),
        ),
        patch("app.features.sessions.repository.SessionRepository.update_session", AsyncMock()),
        patch(
            "app.features.sessions.repository.SessionRepository.complete_session_transaction",
            AsyncMock(return_value=completed_session),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            # 1. Create Session
            create_resp = await client.post(
                "/api/v1/sessions",
                json={
                    "activity_id": "running",
                    "match_mode": "content_first",
                    "content_id": "fx:50",
                },
            )
            assert create_resp.status_code == 201
            c_data = create_resp.json()
            assert c_data["status"] == "success"
            assert c_data["data"]["duration_seconds"] == 1800
            assert c_data["data"]["status"] == "pending"

            # 2. Start Session
            start_resp = await client.post(
                f"/api/v1/sessions/{pending_session.id}/start",
            )
            assert start_resp.status_code == 200
            s_data = start_resp.json()
            assert s_data["status"] == "success"

            # 3. Complete Session
            complete_resp = await client.post(
                f"/api/v1/sessions/{pending_session.id}/complete",
                json={},
            )
            assert complete_resp.status_code == 200
            comp_data = complete_resp.json()
            assert comp_data["status"] == "success"
            assert comp_data["data"]["status"] == "completed"
            assert comp_data["data"]["completed_at"] is not None
