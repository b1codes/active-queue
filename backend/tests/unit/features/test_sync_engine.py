from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.content.models import Source
from app.features.content.service import ContentService


@pytest.mark.asyncio
async def test_sync_source_chunk_single_page() -> None:
    """sync_source_chunk completes small playlist sync in one chunk."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()
    mock_content_repo.upsert_content_cache_batch = AsyncMock()
    mock_content_repo.upsert_feed_items_batch = AsyncMock()

    source = Source(
        id="u1_fixture_fixture-small-playlist",
        user_id="u1",
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Small Playlist",
        status="active",
    )
    mock_source_repo.get_source = AsyncMock(return_value=source)
    mock_source_repo.update_source = AsyncMock()

    service = ContentService(mock_source_repo, mock_content_repo)
    res = await service.sync_source_chunk("u1", source.id)

    assert res.status == "active"
    assert res.items_synced == 15
    assert res.has_more is False
    assert res.next_page_token is None


@pytest.mark.asyncio
async def test_sync_source_chunk_1200_items_multichunk_completion() -> None:
    """1,000+ item fixture playlist syncs to completion across multiple chunks per Milestone 2 criteria."""
    mock_source_repo = MagicMock()
    mock_content_repo = MagicMock()
    mock_content_repo.upsert_content_cache_batch = AsyncMock()
    mock_content_repo.upsert_feed_items_batch = AsyncMock()

    source = Source(
        id="u1_fixture_fixture-large-playlist",
        user_id="u1",
        provider="fixture",
        external_source_id="fixture-large-playlist",
        title="Large Playlist",
        status="active",
        item_count=1200,
    )
    mock_source_repo.get_source = AsyncMock(return_value=source)

    def fake_update(s_id: str, updates: dict) -> None:
        if "status" in updates:
            source.status = updates["status"]
        if "next_page_token" in updates:
            source.next_page_token = updates["next_page_token"]
        if "last_sync_at" in updates:
            source.last_sync_at = updates["last_sync_at"]

    mock_source_repo.update_source = AsyncMock(side_effect=fake_update)

    service = ContentService(mock_source_repo, mock_content_repo)

    # Chunk 1 (0 -> 250 items)
    res1 = await service.sync_source_chunk("u1", source.id)
    assert res1.status == "syncing"
    assert res1.items_synced == 250
    assert res1.has_more is True
    assert res1.next_page_token == "250"

    # Chunk 2 (250 -> 500 items)
    res2 = await service.sync_source_chunk("u1", source.id)
    assert res2.status == "syncing"
    assert res2.items_synced == 250
    assert res2.has_more is True
    assert res2.next_page_token == "500"

    # Chunk 3 (500 -> 750 items)
    res3 = await service.sync_source_chunk("u1", source.id)
    assert res3.items_synced == 250
    assert res3.next_page_token == "750"

    # Chunk 4 (750 -> 1000 items)
    res4 = await service.sync_source_chunk("u1", source.id)
    assert res4.items_synced == 250
    assert res4.next_page_token == "1000"

    # Chunk 5 (1000 -> 1200 items, walk completes!)
    res5 = await service.sync_source_chunk("u1", source.id)
    assert res5.status == "active"
    assert res5.items_synced == 200
    assert res5.has_more is False
    assert res5.next_page_token is None


@pytest.mark.asyncio
async def test_sync_source_preflight_no_change() -> None:
    """Preflight change detection skips page walking when itemCount matches and synced < 7 days ago."""
    mock_source_repo = MagicMock()
    now = datetime.now(UTC)
    recent_sync = now - timedelta(hours=24)

    source = Source(
        id="u1_fixture_fixture-small-playlist",
        user_id="u1",
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Small Playlist",
        item_count=15,
        status="active",
        last_sync_at=recent_sync,
    )
    mock_source_repo.get_source = AsyncMock(return_value=source)
    mock_source_repo.update_source = AsyncMock()

    service = ContentService(mock_source_repo)
    res = await service.sync_source_chunk("u1", source.id)

    assert res.items_synced == 0
    assert res.has_more is False
    assert "No changes detected" in (res.message or "")


@pytest.mark.asyncio
async def test_sync_stalled_expiration() -> None:
    """Stalled sync older than 1 hour expires and resets cursor."""
    mock_source_repo = MagicMock()
    now = datetime.now(UTC)
    stalled_time = now - timedelta(hours=2)

    source = Source(
        id="u1_fixture_fixture-small-playlist",
        user_id="u1",
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Small Playlist",
        status="syncing",
        next_page_token="50",
        updated_at=stalled_time,
    )
    mock_source_repo.get_source = AsyncMock(return_value=source)
    mock_source_repo.update_source = AsyncMock()

    service = ContentService(mock_source_repo)
    res = await service.sync_source_chunk("u1", source.id)

    # Re-synced small playlist cleanly
    assert res.status == "active"
    assert res.items_synced == 15
    assert res.has_more is False
