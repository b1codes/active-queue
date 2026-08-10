from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.content.models import ContentCacheItem, FeedItem
from app.features.content.repository import ContentRepository


def test_content_cache_item_roundtrip() -> None:
    """ContentCacheItem serializes to and deserializes from Firestore data."""
    item = ContentCacheItem(
        content_id="yt:dQw4w9WgXcQ",
        provider="youtube",
        external_id="dQw4w9WgXcQ",
        title="Never Gonna Give You Up",
        duration_seconds=212,
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    firestore_dict = item.to_firestore()
    assert firestore_dict["content_id"] == "yt:dQw4w9WgXcQ"
    assert firestore_dict["provider"] == "youtube"

    reconstructed = ContentCacheItem.from_firestore(firestore_dict)
    assert reconstructed.content_id == item.content_id
    assert reconstructed.duration_seconds == 212


def test_feed_item_roundtrip() -> None:
    """FeedItem serializes to and deserializes from Firestore data with deterministic ID."""
    feed_item = FeedItem(
        id="user123_yt:dQw4w9WgXcQ",
        user_id="user123",
        content_id="yt:dQw4w9WgXcQ",
        source_id="PL123",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        duration_seconds=212,
        consumed=False,
    )
    firestore_dict = feed_item.to_firestore()
    assert firestore_dict["id"] == "user123_yt:dQw4w9WgXcQ"
    assert firestore_dict["consumed"] is False

    reconstructed = FeedItem.from_firestore(firestore_dict)
    assert reconstructed.id == feed_item.id
    assert reconstructed.user_id == "user123"


@pytest.mark.asyncio
async def test_content_repository_upsert_content_cache() -> None:
    """ContentRepository.upsert_content_cache_batch executes batch writes."""
    mock_client = MagicMock()
    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_client.batch.return_value = mock_batch

    mock_doc = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = ContentRepository(mock_client)
    item = ContentCacheItem(
        content_id="fx:123",
        provider="fixture",
        external_id="123",
        title="Test",
        duration_seconds=300,
        published_at=datetime.now(UTC),
    )

    await repo.upsert_content_cache_batch([item])
    assert mock_batch.commit.called


@pytest.mark.asyncio
async def test_content_repository_get_content_cache_batch() -> None:
    """ContentRepository.get_content_cache_batch fetches items via get_all."""
    mock_client = MagicMock()
    item1 = ContentCacheItem(
        content_id="fx:1",
        provider="fixture",
        external_id="1",
        title="Video 1",
        duration_seconds=300,
        published_at=datetime.now(UTC),
    )
    snap1 = MagicMock()
    snap1.exists = True
    snap1.to_dict.return_value = item1.to_firestore()

    async def async_generator(refs: list[MagicMock]) -> AsyncGenerator[MagicMock, None]:
        yield snap1

    mock_client.get_all = async_generator
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection

    repo = ContentRepository(mock_client)
    res = await repo.get_content_cache_batch(["fx:1"])
    assert "fx:1" in res
    assert res["fx:1"].title == "Video 1"


@pytest.mark.asyncio
async def test_content_repository_upsert_feed_items_idempotency() -> None:
    """ContentRepository.upsert_feed_items_batch uses deterministic doc ID for idempotency."""
    mock_client = MagicMock()
    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_client.batch.return_value = mock_batch

    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection

    repo = ContentRepository(mock_client)
    feed_item = FeedItem(
        id="u1_fx:123",
        user_id="u1",
        content_id="fx:123",
        source_id="src1",
        published_at=datetime.now(UTC),
        duration_seconds=300,
    )

    await repo.upsert_feed_items_batch([feed_item])
    mock_collection.document.assert_called_with("u1_fx:123")
    assert mock_batch.commit.called


@pytest.mark.asyncio
async def test_content_repository_get_user_feed_items() -> None:
    """ContentRepository.get_user_feed_items queries unconsumed feed items."""
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query

    item1 = FeedItem(
        id="u1_fx:1",
        user_id="u1",
        content_id="fx:1",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=300,
    )
    snap1 = MagicMock()
    snap1.to_dict.return_value = item1.to_firestore()

    mock_query.get = AsyncMock(return_value=[snap1])
    mock_client.collection.return_value = mock_query

    repo = ContentRepository(mock_client)
    results, _next_cursor = await repo.get_user_feed_items_page("u1", limit=10)

    assert len(results) == 1
    assert results[0].content_id == "fx:1"


@pytest.mark.asyncio
async def test_content_repository_mark_feed_item_consumed() -> None:
    """ContentRepository.mark_feed_item_consumed sets consumed = True on document."""
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.update = AsyncMock()
    snap = MagicMock()
    snap.exists = True
    mock_doc.get = AsyncMock(return_value=snap)

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection

    repo = ContentRepository(mock_client)
    await repo.mark_feed_item_consumed("u1", "fx:100")

    mock_collection.document.assert_called_with("u1_fx:100")
    mock_doc.update.assert_called_with({"consumed": True})
