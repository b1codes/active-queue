from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_returns_200_when_firestore_reachable(
    client: AsyncClient,
    mock_firestore_client: MagicMock,
) -> None:
    """GET /healthz returns 200 with healthy status when Firestore is reachable."""
    response = await client.get("/healthz")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "healthy"
    assert data["data"]["firestore"]["status"] == "up"
    assert "latency_ms" in data["data"]["firestore"]
    assert data["data"]["provider"]["status"] == "unknown"


@pytest.mark.asyncio
async def test_healthz_returns_503_when_firestore_unreachable(
    client: AsyncClient,
    mock_firestore_client: MagicMock,
) -> None:
    """GET /healthz returns 503 when Firestore sentinel read fails."""
    # Make the sentinel document read raise an exception
    mock_doc_ref = MagicMock()
    mock_doc_ref.get = AsyncMock(side_effect=Exception("Connection refused"))
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_firestore_client.collection.return_value = mock_collection

    response = await client.get("/healthz")
    assert response.status_code == 503

    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "SERVICE_UNAVAILABLE"
