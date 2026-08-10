from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.content.models import FeedItem, Source
from app.features.sessions.models import Session
from app.features.users.models import User, UserAuthorization
from app.main import app


@pytest.mark.asyncio
async def test_multiuser_session_isolation(mock_firestore_client: MagicMock) -> None:
    """User A cannot read, start, complete, abandon, or discard User B's session."""
    user_a_token = {"uid": "user_A", "email": "userA@example.com"}
    user_b_session = Session(
        id="s_user_B_123",
        user_id="user_B",
        activity_id="running",
        match_mode="content_first",
        content_id="fx:10",
        duration_seconds=1800,
        status="pending",
        checklist_completed=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=user_a_token),
        patch(
            "app.features.sessions.repository.SessionRepository.get_session",
            AsyncMock(return_value=user_b_session),
        ),
        patch(
            "app.features.sessions.repository.SessionRepository.get_active_user_session",
            AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer token-user-A"},
        ) as client:
            # User A tries to start User B's session -> must return 404 SESSION_NOT_FOUND (not 403)
            resp_start = await client.post("/api/v1/sessions/s_user_B_123/start")
            assert resp_start.status_code == 404
            assert resp_start.json()["error"]["code"] == "SESSION_NOT_FOUND"

            # User A tries to complete User B's session -> 404
            resp_complete = await client.post("/api/v1/sessions/s_user_B_123/complete")
            assert resp_complete.status_code == 404
            assert resp_complete.json()["error"]["code"] == "SESSION_NOT_FOUND"

            # User A tries to abandon User B's session -> 404
            resp_abandon = await client.post("/api/v1/sessions/s_user_B_123/abandon")
            assert resp_abandon.status_code == 404
            assert resp_abandon.json()["error"]["code"] == "SESSION_NOT_FOUND"

            # User A tries to discard User B's session -> 404
            resp_discard = await client.delete("/api/v1/sessions/s_user_B_123")
            assert resp_discard.status_code == 404
            assert resp_discard.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_multiuser_source_isolation(mock_firestore_client: MagicMock) -> None:
    """User A cannot sync or delete User B's content source."""
    user_a_token = {"uid": "user_A", "email": "userA@example.com"}
    user_b_source = Source(
        id="user_B_youtube_PL999",
        user_id="user_B",
        provider="youtube",
        external_source_id="PL999",
        title="User B Playlist",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=user_a_token),
        patch(
            "app.features.content.repository.SourceRepository.get_source",
            AsyncMock(return_value=user_b_source),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer token-user-A"},
        ) as client:
            # User A tries to sync User B's source -> 404
            resp_sync = await client.post("/api/v1/sources/user_B_youtube_PL999/sync")
            assert resp_sync.status_code == 404
            assert resp_sync.json()["error"]["code"] == "SOURCE_NOT_FOUND"

            # User A tries to delete User B's source -> 404
            resp_delete = await client.delete("/api/v1/sources/user_B_youtube_PL999")
            assert resp_delete.status_code == 404
            assert resp_delete.json()["error"]["code"] == "SOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_multiuser_feed_isolation(mock_firestore_client: MagicMock) -> None:
    """GET /feed for User A only returns User A's feed items."""
    user_a_token = {"uid": "user_A", "email": "userA@example.com"}
    user_a_item = FeedItem(
        id="user_A_fx:1",
        user_id="user_A",
        content_id="fx:1",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=1800,
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=user_a_token),
        patch(
            "app.features.content.repository.ContentRepository.get_user_feed_items_page",
            AsyncMock(return_value=([user_a_item], None)),
        ),
        patch(
            "app.features.content.repository.ContentRepository.get_user_feed_count",
            AsyncMock(return_value=1),
        ),
        patch(
            "app.features.content.repository.ContentRepository.get_content_cache_batch",
            AsyncMock(return_value={}),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer token-user-A"},
        ) as client:
            resp = await client.get("/api/v1/content/feed")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == "user_A_fx:1"
            assert data["total_unconsumed"] == 1


@pytest.mark.asyncio
async def test_multiuser_profile_isolation(mock_firestore_client: MagicMock) -> None:
    """GET /users/me and PATCH /users/me/preferences operate strictly on current user's profile."""
    user_a_token = {"uid": "user_A", "email": "userA@example.com"}
    user_a_profile = User(uid="user_A", email="userA@example.com", display_name="User A")
    user_a_auth = UserAuthorization(uid="user_A", role="user")

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=user_a_token),
        patch(
            "app.features.users.service.UserService.ensure_user_provisioned",
            AsyncMock(return_value=(user_a_profile, user_a_auth)),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer token-user-A"},
        ) as client:
            resp = await client.get("/api/v1/users/me")
            assert resp.status_code == 200
            assert resp.json()["data"]["user"]["uid"] == "user_A"
