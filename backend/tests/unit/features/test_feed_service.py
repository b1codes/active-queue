from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.content.models import ContentCacheItem, FeedItem
from app.features.content.schemas import format_duration_label
from app.features.content.service import ContentService


def test_format_duration_label_formatting() -> None:
    """format_duration_label formats duration_seconds into human readable labels per SPEC §9.2."""
    assert format_duration_label(2712) == "45m 12s"
    assert format_duration_label(3665) == "1h 1m 5s"
    assert format_duration_label(3600) == "1h 0m"
    assert format_duration_label(120) == "2m 0s"
    assert format_duration_label(45) == "45s"
    assert format_duration_label(0) == "0s"


@pytest.mark.asyncio
async def test_get_user_feed_first_page_count_aggregation() -> None:
    """ContentService.get_user_feed computes total_unconsumed count aggregation on first page (cursor is None)."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()

    mock_content_repo.get_user_feed_count = AsyncMock(return_value=42)

    item = FeedItem(
        id="u1_fx:1",
        user_id="u1",
        content_id="fx:1",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=1200,
    )
    cache_doc = ContentCacheItem(
        content_id="fx:1",
        provider="fixture",
        external_id="1",
        title="Workout Video 1",
        duration_seconds=1200,
        published_at=datetime.now(UTC),
    )

    mock_content_repo.get_user_feed_items_page = AsyncMock(return_value=([item], "token_xyz"))
    mock_content_repo.get_content_cache_batch = AsyncMock(return_value={"fx:1": cache_doc})

    service = ContentService(mock_source_repo, mock_content_repo)
    res = await service.get_user_feed("u1", limit=10, cursor=None)

    assert res.total_unconsumed == 42
    assert res.next_cursor == "token_xyz"
    assert len(res.items) == 1
    assert res.items[0].duration_label == "20m 0s"


@pytest.mark.asyncio
async def test_get_user_feed_subsequent_page_no_count() -> None:
    """ContentService.get_user_feed returns total_unconsumed = None on subsequent pages (cursor is not None)."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()

    item = FeedItem(
        id="u1_fx:2",
        user_id="u1",
        content_id="fx:2",
        source_id="s1",
        published_at=datetime.now(UTC),
        duration_seconds=300,
    )

    mock_content_repo.get_user_feed_items_page = AsyncMock(return_value=([item], None))
    mock_content_repo.get_content_cache_batch = AsyncMock(return_value={})

    service = ContentService(mock_source_repo, mock_content_repo)
    res = await service.get_user_feed("u1", limit=10, cursor="encoded_cursor_str")

    assert res.total_unconsumed is None
    assert res.next_cursor is None
    assert len(res.items) == 1
    assert res.items[0].duration_label == "5m 0s"
