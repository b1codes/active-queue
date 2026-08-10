from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


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

