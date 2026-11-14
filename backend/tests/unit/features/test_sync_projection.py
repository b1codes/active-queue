"""What a sync chunk writes into feed_items: durations and the consumed projection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.features.content.models import ContentCacheItem, FeedItem, Source
from app.features.content.service import ContentService

SOURCE = Source(
    id="u1_fixture_fixture-small-playlist",
    user_id="u1",
    provider="fixture",
    external_source_id="fixture-small-playlist",
    title="Small Playlist",
    status="active",
)
FIRST = "fx:fx_vid_0001"


def _service(
    *, cache: dict[str, ContentCacheItem] | None = None, consumed: list[set[str]] | None = None
) -> tuple[ContentService, MagicMock, AsyncMock]:
    source_repo = MagicMock()
    source_repo.get_source = AsyncMock(return_value=SOURCE.model_copy())
    source_repo.update_source = AsyncMock()

    content_repo = MagicMock()
    content_repo.upsert_content_cache_batch = AsyncMock()
    content_repo.upsert_feed_items_batch = AsyncMock()
    content_repo.mark_feed_items_consumed = AsyncMock()

    async def cache_batch(ids: list[str]) -> dict[str, ContentCacheItem]:
        return {i: (cache or {})[i] for i in ids if i in (cache or {})}

    content_repo.get_content_cache_batch = AsyncMock(side_effect=cache_batch)

    user_repo = AsyncMock()
    user_repo.get_consumed_content_ids.side_effect = consumed or [set(), set()]
    return ContentService(source_repo, content_repo, user_repo), content_repo, user_repo


def _written_feed(content_repo: MagicMock) -> list[FeedItem]:
    return [
        fi for call in content_repo.upsert_feed_items_batch.await_args_list for fi in call.args[0]
    ]


def _legacy_row(**overrides: Any) -> ContentCacheItem:
    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "content_id": FIRST,
        "provider": "fixture",
        "external_id": "fx_vid_0001",
        "title": "Legacy row",
        "duration_seconds": 0,
        "published_at": now,
        "is_available": True,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return ContentCacheItem(**fields)


async def test_a_zero_duration_cache_row_is_refetched_not_turned_into_a_feed_item() -> None:
    service, content_repo, _ = _service(cache={FIRST: _legacy_row()})
    await service.sync_source_chunk("u1", SOURCE.id)

    feed = _written_feed(content_repo)
    assert feed
    assert all(fi.duration_seconds > 0 for fi in feed)
    refreshed = [
        c for call in content_repo.upsert_content_cache_batch.await_args_list for c in call.args[0]
    ]
    assert [c.duration_seconds > 0 for c in refreshed if c.content_id == FIRST] == [True]


async def test_a_fresh_cache_row_with_a_duration_is_still_a_hit() -> None:
    service, content_repo, _ = _service(cache={FIRST: _legacy_row(duration_seconds=1234)})
    await service.sync_source_chunk("u1", SOURCE.id)

    first = [fi for fi in _written_feed(content_repo) if fi.content_id == FIRST]
    assert [fi.duration_seconds for fi in first] == [1234]
    refreshed = [
        c for call in content_repo.upsert_content_cache_batch.await_args_list for c in call.args[0]
    ]
    assert FIRST not in {c.content_id for c in refreshed}


async def test_an_item_hidden_during_the_chunk_is_marked_consumed_again() -> None:
    # Read at chunk start: nothing consumed. Read after the upsert: the user hid FIRST
    # while pages were being fetched, so the upsert just overwrote it with consumed=False.
    service, content_repo, user_repo = _service(consumed=[set(), {FIRST, "fx:not-in-this-chunk"}])
    await service.sync_source_chunk("u1", SOURCE.id)

    assert [fi.consumed for fi in _written_feed(content_repo) if fi.content_id == FIRST] == [False]
    content_repo.mark_feed_items_consumed.assert_awaited_once_with("u1", [FIRST])
    assert user_repo.get_consumed_content_ids.await_count == 2


async def test_nothing_is_rewritten_when_no_hide_landed_during_the_chunk() -> None:
    service, content_repo, _ = _service(consumed=[{FIRST}, {FIRST}])
    await service.sync_source_chunk("u1", SOURCE.id)

    assert [fi.consumed for fi in _written_feed(content_repo) if fi.content_id == FIRST] == [True]
    content_repo.mark_feed_items_consumed.assert_not_awaited()
