from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.features.activities.catalog import PREDEFINED_ACTIVITIES
from app.features.activities.models import Activity
from app.features.content.models import FeedItem

GLOBAL_MIN_DURATION_SECONDS = 300  # 5 minutes per SPEC §5.2
GLOBAL_MAX_DURATION_SECONDS = 10800  # 3 hours per SPEC §5.2

PRIMARY_WINDOW_OFFSET_SECONDS = 300  # +5 minutes [B, B+300] per SPEC §5.3
FALLBACK_WINDOW_OFFSET_SECONDS = 120  # -2 minutes [B-120, B) per SPEC §5.3

RejectionReason = Literal["duration_out_of_range", "no_matching_activity", "no_content_in_window"]
WindowType = Literal["primary", "fallback"]


@dataclass(frozen=True)
class ContentMatchResult:
    """Domain model for content-first activity match result per SPEC §5.2 & §9.6."""

    content_id: str
    duration_seconds: int
    matching_activities: list[Activity]
    is_valid: bool
    rejection_reason: RejectionReason | None = None


@dataclass(frozen=True)
class TimeMatchResult:
    """Domain model for time-first content match result per SPEC §5.3 & §9.6.

    Asymmetric windows:
    - Primary: [B, B+300] ranked ascending by duration_seconds (closest to target B first).
    - Fallback: [B-120, B) ranked descending by duration_seconds (closest to target B first),
      used ONLY if primary window is empty.
    """

    target_duration_seconds: int
    matched_items: list[FeedItem]
    window_type: WindowType | None
    is_valid: bool
    rejection_reason: RejectionReason | None = None


def match_content_to_activities(
    content_id: str,
    duration_seconds: int,
    catalog: list[Activity] | None = None,
) -> ContentMatchResult:
    """Match content duration exactly against physical activity catalog per SPEC §5.2 & §9.6."""
    if catalog is None:
        catalog = PREDEFINED_ACTIVITIES

    if (
        duration_seconds < GLOBAL_MIN_DURATION_SECONDS
        or duration_seconds > GLOBAL_MAX_DURATION_SECONDS
    ):
        return ContentMatchResult(
            content_id=content_id,
            duration_seconds=duration_seconds,
            matching_activities=[],
            is_valid=False,
            rejection_reason="duration_out_of_range",
        )

    matching = [
        act
        for act in catalog
        if act.is_active
        and act.min_duration_seconds <= duration_seconds <= act.max_duration_seconds
    ]

    if not matching:
        return ContentMatchResult(
            content_id=content_id,
            duration_seconds=duration_seconds,
            matching_activities=[],
            is_valid=False,
            rejection_reason="no_matching_activity",
        )

    return ContentMatchResult(
        content_id=content_id,
        duration_seconds=duration_seconds,
        matching_activities=matching,
        is_valid=True,
        rejection_reason=None,
    )


def match_time_block_asymmetric(
    target_duration_seconds: int,
    unconsumed_feed: list[FeedItem],
) -> TimeMatchResult:
    """Execute asymmetric window time-first matching over unconsumed feed items per SPEC §5.3.

    Asymmetry Rationale:
    Content slightly longer than the block ends with a little content left — harmless.
    Content shorter means silence during the final stretch — exact failure mode app exists to prevent.
    Overshoot preferred ([B, B+300]), undershoot capped at 2 mins ([B-120, B)).
    """
    b = target_duration_seconds

    # 1. Primary Window: [B, B+300]
    primary_min = b
    primary_max = b + PRIMARY_WINDOW_OFFSET_SECONDS

    primary_candidates = [
        item for item in unconsumed_feed if primary_min <= item.duration_seconds <= primary_max
    ]

    if primary_candidates:
        # Rank ASCENDING by duration_seconds (closest to target B first)
        primary_candidates.sort(key=lambda x: x.duration_seconds)
        return TimeMatchResult(
            target_duration_seconds=b,
            matched_items=primary_candidates,
            window_type="primary",
            is_valid=True,
            rejection_reason=None,
        )

    # 2. Fallback Window: [B-120, B)
    fallback_min = max(300, b - FALLBACK_WINDOW_OFFSET_SECONDS)
    fallback_max = b - 1

    fallback_candidates = [
        item for item in unconsumed_feed if fallback_min <= item.duration_seconds <= fallback_max
    ]

    if fallback_candidates:
        # Rank DESCENDING by duration_seconds (closest to target B first)
        fallback_candidates.sort(key=lambda x: x.duration_seconds, reverse=True)
        return TimeMatchResult(
            target_duration_seconds=b,
            matched_items=fallback_candidates,
            window_type="fallback",
            is_valid=True,
            rejection_reason=None,
        )

    # 3. Empty result: No content in either asymmetric window
    return TimeMatchResult(
        target_duration_seconds=b,
        matched_items=[],
        window_type=None,
        is_valid=False,
        rejection_reason="no_content_in_window",
    )
