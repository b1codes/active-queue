from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cli.seed import clear_collections, main, seed_db, seed_firebase_auth


@pytest.mark.asyncio
async def test_seed_firebase_auth_create_and_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test seed_firebase_auth creates new users and updates existing users."""
    mock_auth = MagicMock()
    # First user throws UserNotFoundError (so it creates), second user exists (so it updates)
    from firebase_admin.exceptions import FirebaseError

    class UserNotFoundError(FirebaseError):
        def __init__(self) -> None:
            super().__init__(code="NOT_FOUND", message="User not found")

    mock_auth.UserNotFoundError = UserNotFoundError
    mock_auth.get_user.side_effect = [UserNotFoundError(), MagicMock()]

    monkeypatch.setattr("firebase_admin.auth", mock_auth)

    users = [
        {"uid": "user-1", "email": "u1@example.com", "display_name": "User One"},
        {"uid": "user-2", "email": "u2@example.com", "display_name": "User Two"},
    ]

    with patch("app.cli.seed.init_firebase_admin"):
        count = await seed_firebase_auth(users, quiet=True)

    assert count == 2
    assert mock_auth.create_user.call_count == 1
    assert mock_auth.update_user.call_count == 1


@pytest.mark.asyncio
async def test_clear_collections() -> None:
    """Test clear_collections deletes documents across target collections."""
    mock_db = MagicMock()
    mock_doc1 = MagicMock()
    mock_doc2 = MagicMock()
    mock_coll = MagicMock()

    # AsyncMock for query get()
    mock_coll.get = AsyncMock(return_value=[mock_doc1, mock_doc2])
    mock_db.collection.return_value = mock_coll

    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_db.batch.return_value = mock_batch

    await clear_collections(mock_db, quiet=True)

    assert mock_coll.get.call_count == 6  # 6 collections cleared
    assert mock_batch.delete.call_count == 12  # 2 docs x 6 collections
    assert mock_batch.commit.call_count == 6


@pytest.mark.asyncio
async def test_seed_db_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full seed_db execution flow with Firestore mock."""
    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_db.batch.return_value = mock_batch

    mock_coll = MagicMock()
    mock_coll.get = AsyncMock(return_value=[])
    mock_db.collection.return_value = mock_coll

    monkeypatch.setattr("app.cli.seed.init_firestore", AsyncMock())
    monkeypatch.setattr("app.cli.seed.close_firestore", AsyncMock())
    monkeypatch.setattr("app.cli.seed.get_firestore_client", lambda: mock_db)
    monkeypatch.setattr("app.cli.seed.seed_firebase_auth", AsyncMock(return_value=2))

    counts = await seed_db(clear=True, primary_user_id="test-user-123", quiet=True)

    assert counts["users"] == 2
    assert counts["authorizations"] == 2
    assert counts["auth_emulator_users"] == 2
    assert counts["sources"] == 3
    assert counts["content_cache"] == 80
    assert counts["feed_items"] == 100
    assert counts["sessions"] == 12


def test_seed_cli_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI main entrypoint parsing."""
    mock_seed_db = AsyncMock(return_value={})
    monkeypatch.setattr("app.cli.seed.seed_db", mock_seed_db)
    monkeypatch.setattr("sys.argv", ["seed.py", "--clear", "--user-id", "custom-uid", "--quiet"])

    main()

    mock_seed_db.assert_called_once_with(
        clear=True,
        primary_user_id="custom-uid",
        quiet=True,
    )
