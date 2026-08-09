from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.users.cache import AuthorizationCache
from app.features.users.models import UserAuthorization
from app.features.users.repository import UserRepository


def test_authorization_cache_hit_and_miss() -> None:
    """AuthorizationCache returns cached value on hit, None on miss or expiration."""
    cache = AuthorizationCache(ttl_seconds=60, max_entries=100)
    auth = UserAuthorization(uid="u1", role="user")

    # Miss before set
    assert cache.get("u1") is None

    # Set and hit
    cache.set("u1", auth)
    cached = cache.get("u1")
    assert cached is not None
    assert cached.uid == "u1"


def test_authorization_cache_ttl_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    """AuthorizationCache evicts entries after TTL expires."""
    cache = AuthorizationCache(ttl_seconds=10, max_entries=100)
    auth = UserAuthorization(uid="u1", role="user")

    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("u1", auth)
    assert cache.get("u1") is not None

    # Advance time beyond 10s TTL
    current_time = 1015.0
    assert cache.get("u1") is None


def test_authorization_cache_lru_eviction() -> None:
    """AuthorizationCache evicts oldest item when max_entries is exceeded."""
    cache = AuthorizationCache(ttl_seconds=60, max_entries=2)
    a1 = UserAuthorization(uid="u1")
    a2 = UserAuthorization(uid="u2")
    a3 = UserAuthorization(uid="u3")

    cache.set("u1", a1)
    cache.set("u2", a2)
    assert len(cache) == 2

    # Setting 3rd item evicts u1 (oldest)
    cache.set("u3", a3)
    assert len(cache) == 2
    assert cache.get("u1") is None
    assert cache.get("u2") is not None
    assert cache.get("u3") is not None


def test_authorization_cache_invalidate_and_clear() -> None:
    """AuthorizationCache supports manual entry invalidation and clear."""
    cache = AuthorizationCache(ttl_seconds=60, max_entries=100)
    cache.set("u1", UserAuthorization(uid="u1"))
    cache.set("u2", UserAuthorization(uid="u2"))

    cache.invalidate("u1")
    assert cache.get("u1") is None
    assert cache.get("u2") is not None

    cache.clear()
    assert len(cache) == 0


@pytest.mark.asyncio
async def test_user_repository_uses_auth_cache() -> None:
    """UserRepository.get_authorization uses in-process auth_cache on hits."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock()

    auth_doc = UserAuthorization(uid="cached_user", role="admin")
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = auth_doc.to_firestore()
    mock_doc.get.return_value = mock_snap

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = UserRepository(mock_client)

    # First call — cache miss, reads Firestore
    res1 = await repo.get_authorization("cached_user", use_cache=True)
    assert res1 is not None
    assert res1.uid == "cached_user"
    assert mock_doc.get.call_count == 1

    # Second call — cache hit, does NOT read Firestore again
    res2 = await repo.get_authorization("cached_user", use_cache=True)
    assert res2 is not None
    assert res2.uid == "cached_user"
    assert mock_doc.get.call_count == 1
