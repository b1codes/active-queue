from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from app.core.dependencies import get_db

if TYPE_CHECKING:
    import pytest


def test_get_db_yields_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db dependency yields the firestore client."""
    mock_client = MagicMock()
    monkeypatch.setattr("app.core.dependencies.get_firestore_client", lambda: mock_client)

    gen = get_db()
    client = next(gen)
    assert client is mock_client
