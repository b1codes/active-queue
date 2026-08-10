from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import AuthorizationError, NotFoundError
from app.core.security import AuthenticatedUser
from app.features.users.models import User, UserAuthorization
from app.features.users.repository import UserRepository
from app.features.users.schemas import (
    UpdatePreferencesRequest,
    UserAuthorizationSchema,
    UserSchema,
)
from app.features.users.service import UserService


def test_user_model_firestore_roundtrip() -> None:
    """User domain model serializes to and deserializes from Firestore data."""
    u = User(
        uid="user_100",
        email="runner@example.com",
        display_name="Speedy Runner",
        photo_url="https://example.com/avatar.jpg",
    )
    firestore_dict = u.to_firestore()
    assert firestore_dict["uid"] == "user_100"
    assert firestore_dict["email"] == "runner@example.com"
    assert firestore_dict["preferences"]["dark_mode"] is True

    reconstructed = User.from_firestore(firestore_dict)
    assert reconstructed.uid == u.uid
    assert reconstructed.email == u.email
    assert reconstructed.display_name == u.display_name


def test_user_authorization_model_roundtrip() -> None:
    """UserAuthorization domain model serializes and deserializes correctly."""
    auth_model = UserAuthorization(
        uid="user_100",
        role="admin",
        status="active",
        disabled=False,
    )
    firestore_dict = auth_model.to_firestore()
    assert firestore_dict["role"] == "admin"
    assert firestore_dict["status"] == "active"

    reconstructed = UserAuthorization.from_firestore(firestore_dict)
    assert reconstructed.uid == auth_model.uid
    assert reconstructed.role == auth_model.role


def test_user_schemas_from_domain() -> None:
    """UserSchema and UserAuthorizationSchema map correctly from domain models."""
    u = User(uid="u1", email="a@b.com", display_name="Test")
    user_schema = UserSchema.from_domain(u)
    assert user_schema.uid == "u1"
    assert user_schema.display_name == "Test"

    a = UserAuthorization(uid="u1", role="user")
    auth_schema = UserAuthorizationSchema.from_domain(a)
    assert auth_schema.uid == "u1"
    assert auth_schema.role == "user"

    update_req = UpdatePreferencesRequest(
        preferred_tracker_app="strava",
        default_time_block_seconds=3600,
    )
    assert update_req.preferred_tracker_app == "strava"
    assert update_req.default_time_block_seconds == 3600


@pytest.mark.asyncio
async def test_user_repository_get_user() -> None:
    """UserRepository.get_user returns User model or None if missing."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock()

    # Document missing
    mock_snap_missing = MagicMock()
    mock_snap_missing.exists = False
    mock_doc.get.return_value = mock_snap_missing

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    res = await repo.get_user("nonexistent")
    assert res is None

    # Document present
    u = User(uid="user_123", email="test@example.com", display_name="Test")
    mock_snap_present = MagicMock()
    mock_snap_present.exists = True
    mock_snap_present.to_dict.return_value = u.to_firestore()
    mock_doc.get.return_value = mock_snap_present

    res_present = await repo.get_user("user_123")
    assert res_present is not None
    assert res_present.uid == "user_123"


@pytest.mark.asyncio
async def test_user_repository_get_authorization() -> None:
    """UserRepository.get_authorization returns UserAuthorization or None if missing."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock()

    mock_snap_missing = MagicMock()
    mock_snap_missing.exists = False
    mock_doc.get.return_value = mock_snap_missing

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    res = await repo.get_authorization("nonexistent")
    assert res is None


@pytest.mark.asyncio
async def test_user_repository_provision_user_transactional() -> None:
    """UserRepository.provision_user_transactional commits batch writes."""
    mock_client = MagicMock()
    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_client.batch.return_value = mock_batch

    mock_doc = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    u = User(uid="u1", email="a@b.com", display_name="Test")
    a = UserAuthorization(uid="u1")

    res_u, res_a = await repo.provision_user_transactional(u, a)
    assert res_u.uid == "u1"
    assert res_a.uid == "u1"
    assert mock_batch.commit.called


@pytest.mark.asyncio
async def test_user_repository_update_user() -> None:
    """UserRepository.update_user updates fields and returns updated User."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.update = AsyncMock()

    u = User(uid="u1", email="a@b.com", display_name="Original")
    u_updated = User(uid="u1", email="a@b.com", display_name="Updated")

    snap1 = MagicMock()
    snap1.exists = True
    snap1.to_dict.return_value = u.to_firestore()

    snap2 = MagicMock()
    snap2.exists = True
    snap2.to_dict.return_value = u_updated.to_firestore()

    mock_doc.get = AsyncMock(side_effect=[snap1, snap2])

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    updated = await repo.update_user("u1", {"display_name": "Updated"})
    assert updated is not None
    assert updated.display_name == "Updated"


@pytest.mark.asyncio
async def test_user_repository_update_user_nonexistent_returns_none() -> None:
    """UserRepository.update_user returns None if user does not exist."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    snap = MagicMock()
    snap.exists = False
    mock_doc.get = AsyncMock(return_value=snap)

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    updated = await repo.update_user("nonexistent", {"display_name": "New"})
    assert updated is None


@pytest.mark.asyncio
async def test_ensure_user_provisioned_first_login() -> None:
    """First-login provisions users/{uid} and user_authorization/{uid} atomically."""
    mock_repo = MagicMock()
    mock_repo.get_authorization = AsyncMock(return_value=None)
    mock_repo.get_user = AsyncMock(return_value=None)

    async def mock_provision(u: User, a: UserAuthorization) -> tuple[User, UserAuthorization]:
        return u, a

    mock_repo.provision_user_transactional = AsyncMock(side_effect=mock_provision)

    service = UserService(mock_repo)
    auth_user = AuthenticatedUser(
        uid="new_user_1",
        email="new@example.com",
        name="New User",
    )

    user, user_auth = await service.ensure_user_provisioned(auth_user)

    assert user.uid == "new_user_1"
    assert user.email == "new@example.com"
    assert user.display_name == "New User"
    assert user_auth.uid == "new_user_1"
    assert user_auth.status == "active"
    assert mock_repo.provision_user_transactional.called


@pytest.mark.asyncio
async def test_ensure_user_provisioned_disabled_account_raises_authorization_error() -> None:
    """Disabled account raises AuthorizationError(code="ACCOUNT_DISABLED")."""
    disabled_auth = UserAuthorization(
        uid="disabled_user",
        status="disabled",
        disabled=True,
    )
    mock_repo = MagicMock()
    mock_repo.get_authorization = AsyncMock(return_value=disabled_auth)
    mock_repo.get_user = AsyncMock(return_value=None)

    service = UserService(mock_repo)
    auth_user = AuthenticatedUser(uid="disabled_user", email="disabled@example.com")

    with pytest.raises(AuthorizationError) as exc_info:
        await service.ensure_user_provisioned(auth_user)

    assert exc_info.value.code == "ACCOUNT_DISABLED"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_user_repository_is_consumed_and_mark_consumed() -> None:
    """UserRepository.is_consumed and mark_consumed manage consumed_content_ids."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.update = AsyncMock()

    u = User(uid="u1", email="a@b.com", display_name="Test", consumed_content_ids=["vid_100"])
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = u.to_firestore()
    mock_doc.get = AsyncMock(return_value=snap)

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)
    assert await repo.is_consumed("u1", "vid_100") is True
    assert await repo.is_consumed("u1", "vid_200") is False

    await repo.mark_consumed("u1", "vid_200")
    assert mock_doc.update.called


@pytest.mark.asyncio
async def test_get_user_profile_success_and_not_found() -> None:
    """UserService.get_user_profile returns User or raises NotFoundError."""
    mock_repo = MagicMock()
    u = User(uid="u1", email="a@b.com", display_name="Test")
    mock_repo.get_user = AsyncMock(return_value=u)

    service = UserService(mock_repo)
    found = await service.get_user_profile("u1")
    assert found.uid == "u1"

    mock_repo.get_user = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError) as exc_info:
        await service.get_user_profile("missing")
    assert exc_info.value.code == "USER_NOT_FOUND"
