from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from firebase_admin import auth

from app.core.errors import AuthenticationError
from app.core.security import AuthenticatedUser, get_current_user, init_firebase_admin


def test_init_firebase_admin_sets_emulator_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_firebase_admin sets FIREBASE_AUTH_EMULATOR_HOST environment variable."""
    from app.core.config import Settings

    s = Settings(env="local", firebase_auth_emulator_host="localhost:9099")
    init_firebase_admin(s)
    assert os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == "localhost:9099"


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials() -> None:
    """get_current_user raises AUTH_TOKEN_MISSING when credentials are missing."""
    request = MagicMock()
    with pytest.raises(AuthenticationError) as exc_info:
        await get_current_user(request, credentials=None)

    assert exc_info.value.code == "AUTH_TOKEN_MISSING"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_expired_token() -> None:
    """get_current_user raises AUTH_TOKEN_EXPIRED when token has expired."""
    request = MagicMock()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired.jwt.token")

    with (
        patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=auth.ExpiredIdTokenError("Token expired", cause=None),
        ),
        pytest.raises(AuthenticationError) as exc_info,
    ):
        await get_current_user(request, credentials=creds)

    assert exc_info.value.code == "AUTH_TOKEN_EXPIRED"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token() -> None:
    """get_current_user raises AUTH_TOKEN_INVALID when token verification fails."""
    request = MagicMock()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.jwt.token")

    with (
        patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=auth.InvalidIdTokenError("Invalid token"),
        ),
        pytest.raises(AuthenticationError) as exc_info,
    ):
        await get_current_user(request, credentials=creds)

    assert exc_info.value.code == "AUTH_TOKEN_INVALID"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_success() -> None:
    """get_current_user returns AuthenticatedUser and binds uid to request.state."""
    request = MagicMock()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid.jwt.token")
    mock_decoded = {
        "uid": "user_12345",
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/pic.png",
        "email_verified": True,
    }

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
        user = await get_current_user(request, credentials=creds)

    assert isinstance(user, AuthenticatedUser)
    assert user.uid == "user_12345"
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.picture == "https://example.com/pic.png"
    assert user.email_verified is True
    assert request.state.uid == "user_12345"
