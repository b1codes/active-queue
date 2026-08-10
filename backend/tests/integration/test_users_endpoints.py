from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.users.models import User, UserAuthorization
from app.main import app


@pytest.mark.asyncio
async def test_get_users_me_unauthenticated() -> None:
    """GET /api/v1/users/me without token returns 401 AUTH_TOKEN_MISSING."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/users/me")

    assert res.status_code == 401
    body = res.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


@pytest.mark.asyncio
async def test_get_users_me_authenticated_success(
    mock_firestore_client: AsyncMock,
) -> None:
    """GET /api/v1/users/me with valid Bearer token provisions and returns user profile."""
    mock_decoded = {
        "uid": "test_user_777",
        "email": "runner@example.com",
        "name": "Test Runner",
    }
    user_doc = User(
        uid="test_user_777",
        email="runner@example.com",
        display_name="Test Runner",
    )
    auth_doc = UserAuthorization(
        uid="test_user_777",
        role="user",
        status="active",
    )

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.users.service.UserService.ensure_user_provisioned",
            new_callable=AsyncMock,
            return_value=(user_doc, auth_doc),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer valid.token.here"},
            )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["data"]["user"]["uid"] == "test_user_777"
    assert body["data"]["user"]["display_name"] == "Test Runner"
    assert body["data"]["authorization"]["status"] == "active"


@pytest.mark.asyncio
async def test_patch_users_me_preferences_success(
    mock_firestore_client: AsyncMock,
) -> None:
    """PATCH /api/v1/users/me/preferences updates user preferences."""
    mock_decoded = {"uid": "test_user_777", "email": "runner@example.com"}
    user_doc = User(uid="test_user_777", email="runner@example.com", display_name="Test Runner")
    auth_doc = UserAuthorization(uid="test_user_777")
    updated_user = User(
        uid="test_user_777",
        email="runner@example.com",
        display_name="Test Runner",
    )
    updated_user.preferences.preferred_tracker_app = "strava"
    updated_user.preferences.default_time_block_seconds = 3600

    with (
        patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded),
        patch(
            "app.features.users.service.UserService.ensure_user_provisioned",
            new_callable=AsyncMock,
            return_value=(user_doc, auth_doc),
        ),
        patch(
            "app.features.users.service.UserService.update_user_preferences",
            new_callable=AsyncMock,
            return_value=updated_user,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.patch(
                "/api/v1/users/me/preferences",
                headers={"Authorization": "Bearer valid.token.here"},
                json={
                    "preferred_tracker_app": "strava",
                    "default_time_block_seconds": 3600,
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["data"]["preferences"]["preferred_tracker_app"] == "strava"
    assert body["data"]["preferences"]["default_time_block_seconds"] == 3600
