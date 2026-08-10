from __future__ import annotations

from datetime import UTC, datetime

from app.features.content.matcher import match_time_block_asymmetric
from app.features.content.models import FeedItem


def test_time_match_primary_window_ascending_order() -> None:
    """Primary window [B, B+300] matches items >= B and ranks them ASCENDING by duration."""
    now = datetime.now(UTC)

    item_too_short = FeedItem(
        id="u1_1",
        user_id="u1",
        content_id="fx:1",
        source_id="s1",
        published_at=now,
        duration_seconds=1750,
    )
    item_p1 = FeedItem(
        id="u1_2",
        user_id="u1",
        content_id="fx:2",
        source_id="s1",
        published_at=now,
        duration_seconds=1830,
    )
    item_p2 = FeedItem(
        id="u1_3",
        user_id="u1",
        content_id="fx:3",
        source_id="s1",
        published_at=now,
        duration_seconds=1805,
    )
    item_p3 = FeedItem(
        id="u1_4",
        user_id="u1",
        content_id="fx:4",
        source_id="s1",
        published_at=now,
        duration_seconds=2100,
    )

    feed = [item_too_short, item_p1, item_p2, item_p3]
    res = match_time_block_asymmetric(1800, feed)

    assert res.is_valid is True
    assert res.window_type == "primary"
    assert res.rejection_reason is None
    assert len(res.matched_items) == 3
    # Ascending order: 1805s, 1830s, 2100s
    assert [item.duration_seconds for item in res.matched_items] == [1805, 1830, 2100]


def test_time_match_fallback_window_descending_order() -> None:
    """Fallback window [B-120, B) triggers ONLY when primary is empty and ranks DESCENDING by duration."""
    now = datetime.now(UTC)

    item_fb1 = FeedItem(
        id="u1_1",
        user_id="u1",
        content_id="fx:1",
        source_id="s1",
        published_at=now,
        duration_seconds=1700,
    )
    item_fb2 = FeedItem(
        id="u1_2",
        user_id="u1",
        content_id="fx:2",
        source_id="s1",
        published_at=now,
        duration_seconds=1780,
    )
    item_too_short = FeedItem(
        id="u1_3",
        user_id="u1",
        content_id="fx:3",
        source_id="s1",
        published_at=now,
        duration_seconds=1600,
    )

    feed = [item_fb1, item_fb2, item_too_short]
    res = match_time_block_asymmetric(1800, feed)

    assert res.is_valid is True
    assert res.window_type == "fallback"
    assert res.rejection_reason is None
    assert len(res.matched_items) == 2
    # Descending order (closest to 1800s first): 1780s, 1700s
    assert [item.duration_seconds for item in res.matched_items] == [1780, 1700]


def test_time_match_no_content_in_window() -> None:
    """Returns rejection_reason = no_content_in_window when both asymmetric windows are empty."""
    now = datetime.now(UTC)

    item_too_short = FeedItem(
        id="u1_1",
        user_id="u1",
        content_id="fx:1",
        source_id="s1",
        published_at=now,
        duration_seconds=1200,
    )
    item_too_long = FeedItem(
        id="u1_2",
        user_id="u1",
        content_id="fx:2",
        source_id="s1",
        published_at=now,
        duration_seconds=2500,
    )

    feed = [item_too_short, item_too_long]
    res = match_time_block_asymmetric(1800, feed)

    assert res.is_valid is False
    assert res.window_type is None
    assert res.rejection_reason == "no_content_in_window"
    assert len(res.matched_items) == 0
