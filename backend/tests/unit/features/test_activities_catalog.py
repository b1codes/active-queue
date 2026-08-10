from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.features.activities.catalog import PREDEFINED_ACTIVITIES, PREDEFINED_TIME_BLOCKS
from app.features.activities.service import ActivityService


def test_activities_catalog_has_nine_predefined_activities() -> None:
    """Predefined activity catalog contains exactly 9 activities per SPEC §5.1."""
    assert len(PREDEFINED_ACTIVITIES) == 9
    ids = [act.id for act in PREDEFINED_ACTIVITIES]
    expected = [
        "running",
        "cycling",
        "strength",
        "yoga",
        "pilates",
        "hiit",
        "walking",
        "rowing",
        "meditation",
    ]
    assert sorted(ids) == sorted(expected)


def test_time_blocks_catalog_has_seven_predefined_blocks() -> None:
    """Predefined time blocks catalog contains exactly 7 blocks per SPEC §5.3."""
    assert len(PREDEFINED_TIME_BLOCKS) == 7
    ids = [tb.id for tb in PREDEFINED_TIME_BLOCKS]
    expected = ["tb_15m", "tb_20m", "tb_30m", "tb_45m", "tb_60m", "tb_75m", "tb_90m"]
    assert ids == expected


def test_activity_service_duration_validation() -> None:
    """ActivityService validates min/max duration bounds for activities."""
    service = ActivityService()

    # Valid duration for running (1800s = 30m)
    service.validate_duration("running", 1800)

    # Invalid duration below min for strength (100s < 600s min)
    with pytest.raises(ValidationError) as exc_info:
        service.validate_duration("strength", 100)

    assert exc_info.value.code == "ACTIVITY_DURATION_MISMATCH"
