from __future__ import annotations

from app.features.activities.models import Activity
from app.features.content.matcher import match_content_to_activities


def test_match_content_exact_valid() -> None:
    """1800s (30m) content matches valid activities in catalog."""
    res = match_content_to_activities("fx:1", 1800)
    assert res.is_valid is True
    assert res.rejection_reason is None
    assert len(res.matching_activities) > 0
    act_ids = [act.id for act in res.matching_activities]
    assert "running" in act_ids
    assert "yoga" in act_ids


def test_match_content_duration_out_of_range_too_short() -> None:
    """120s (2m) video returns duration_out_of_range (< 300s min)."""
    res = match_content_to_activities("fx:short", 120)
    assert res.is_valid is False
    assert res.rejection_reason == "duration_out_of_range"
    assert len(res.matching_activities) == 0


def test_match_content_duration_out_of_range_too_long() -> None:
    """14400s (4h) video returns duration_out_of_range (> 10800s max)."""
    res = match_content_to_activities("fx:long", 14400)
    assert res.is_valid is False
    assert res.rejection_reason == "duration_out_of_range"
    assert len(res.matching_activities) == 0


def test_match_content_no_matching_activity() -> None:
    """420s (7m) video is globally valid (300 <= 420 <= 10800) but matches no activity in high-threshold catalog."""
    custom_catalog = [
        Activity(
            id="strength",
            name="Strength Training",
            category="workout",
            tracker="apple_fitness",
            min_duration_seconds=600,
            max_duration_seconds=7200,
            default_duration_seconds=2700,
            icon_name="dumbbell",
        )
    ]
    res = match_content_to_activities("fx:7m", 420, catalog=custom_catalog)
    assert res.is_valid is False
    assert res.rejection_reason == "no_matching_activity"
    assert len(res.matching_activities) == 0
