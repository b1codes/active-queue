from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import AccountStatus, account_status_cache
from app.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Async HTTP client for integration tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def mock_firestore_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the Firestore client returned by get_firestore_client().

    The mock supports the async document.get() call chain used by /healthz.
    """
    mock_client = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc_ref.get = AsyncMock(return_value=MagicMock())
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_client.collection.return_value = mock_collection

    monkeypatch.setattr(
        "app.core.firestore._client",
        mock_client,
    )
    return mock_client


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset rate limiter state before each test for test isolation."""
    from app.middleware.ratelimit import _limiter

    _limiter.reset()


@pytest.fixture(autouse=True)
def reset_health_provider_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """/healthz caches provider reachability for 60s in a module global; never share it."""
    monkeypatch.setattr(
        "app.features.health.router._provider_reachability_cache",
        {"status": "unknown", "checked_at": 0.0},
    )


async def _active_account(_uid: str) -> AccountStatus:
    return AccountStatus(disabled=False, tokens_valid_after_ms=0)


@pytest.fixture(autouse=True)
def firebase_user_record_is_active(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Outside the emulator tier, the Firebase user-record lookup reports an active account.

    Tests that exercise revocation or disabling override fetch_account_status themselves.
    """
    account_status_cache.clear()
    if "emulator" not in request.node.path.parts:
        monkeypatch.setattr("app.core.security.fetch_account_status", _active_account)
    yield
    account_status_cache.clear()
