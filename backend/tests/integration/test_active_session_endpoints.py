from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.sessions.models import Session
from app.main import app


@pytest.mark.asyncio
async def test_get_active_session_and_abandon_endpoints(mock_firestore_client: AsyncMock) -> None:
    """GET /api/v1/sessions/active and POST /api/v1/sessions/{id}/abandon endpoints per SPEC §9.5."""
    mock_decoded = {"uid": "test_user_act_1", "email": "test@example.com"}

    active_session = Session(
        id="s_act_999",
        user_id="test_user_act_1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:10",
        duration_seconds=1800,
        status="in_progress",
        started_at=datetime.now(UTC),
    )

    abandoned_session = Session(
        id="s_act_999",
        user_id="test_user_act_1",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:10",
        duration_seconds=1800,
        status="abandoned",
        abandoned_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.sessions.repository.SessionRepository.get_active_user_session",
            AsyncMock(return_value=active_session),
        ),
        patch(
            "app.features.sessions.repository.SessionRepository.abandon_session",
            AsyncMock(return_value=abandoned_session),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-valid-token"},
        ) as client:
            # 1. GET /sessions/active
            get_resp = await client.get("/api/v1/sessions/active")
            assert get_resp.status_code == 200
            g_data = get_resp.json()
            assert g_data["status"] == "success"
            assert g_data["data"]["id"] == "s_act_999"
            assert g_data["data"]["status"] == "in_progress"

            # 2. POST /sessions/s_act_999/abandon
            abandon_resp = await client.post("/api/v1/sessions/s_act_999/abandon")
            assert abandon_resp.status_code == 200
            a_data = abandon_resp.json()
            assert a_data["status"] == "success"
            assert a_data["data"]["status"] == "abandoned"
            assert a_data["data"]["abandoned_at"] is not None
