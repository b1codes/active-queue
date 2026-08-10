from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.sessions.models import Session
from app.main import app


@pytest.mark.asyncio
async def test_session_history_and_discard_endpoints(mock_firestore_client: AsyncMock) -> None:
    """GET /api/v1/sessions and DELETE /api/v1/sessions/{id} endpoints per Decision #6 & SPEC §9.5."""
    mock_decoded = {"uid": "test_user_hist_1", "email": "test@example.com"}

    hist_session = Session(
        id="s_hist_100",
        user_id="test_user_hist_1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:10",
        duration_seconds=1800,
        status="completed",
        completed_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.sessions.repository.SessionRepository.get_user_sessions_page",
            AsyncMock(return_value=([hist_session], "next_cur_123")),
        ),
        patch(
            "app.features.sessions.repository.SessionRepository.discard_session",
            AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            # 1. GET /sessions history list
            get_resp = await client.get("/api/v1/sessions?limit=10")
            assert get_resp.status_code == 200
            g_data = get_resp.json()
            assert g_data["status"] == "success"
            assert len(g_data["data"]["items"]) == 1
            assert g_data["data"]["items"][0]["id"] == "s_hist_100"
            assert g_data["data"]["next_cursor"] == "next_cur_123"

            # 2. DELETE /sessions/s_pending_1 discard
            del_resp = await client.delete("/api/v1/sessions/s_pending_1")
            assert del_resp.status_code == 200
            d_data = del_resp.json()
            assert d_data["status"] == "success"
            assert d_data["data"]["session_id"] == "s_pending_1"
            assert d_data["data"]["discarded"] is True
