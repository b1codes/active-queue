from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.dependencies import PaginationParams, get_db


def test_pagination_params_defaults() -> None:
    """PaginationParams defaults to limit=20, offset=0."""
    p = PaginationParams()
    assert p.limit == 20
    assert p.offset == 0


def test_pagination_params_bounds() -> None:
    """PaginationParams enforces limit bounds [1, 100] and offset >= 0."""
    p = PaginationParams(limit=50, offset=10)
    assert p.limit == 50
    assert p.offset == 10

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PaginationParams(limit=0)

    with pytest.raises(ValidationError):
        PaginationParams(limit=101)


def test_get_db_yields_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db dependency yields the firestore client."""
    mock_client = MagicMock()
    monkeypatch.setattr("app.core.dependencies.get_firestore_client", lambda: mock_client)

    gen = get_db()
    client = next(gen)
    assert client is mock_client
