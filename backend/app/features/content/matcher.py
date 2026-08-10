from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.features.activities.catalog import PREDEFINED_ACTIVITIES
from app.features.activities.models import Activity

GLOBAL_MIN_DURATION_SECONDS = 300  # 5 minutes per SPEC §5.2
GLOBAL_MAX_DURATION_SECONDS = 10800  # 3 hours per SPEC §5.2

RejectionReason = Literal["duration_out_of_range", "no_matching_activity"]


@dataclass(frozen=True)
class ContentMatchResult:
    """Domain model for content-first activity match result per SPEC §5.2 & §9.6."""

    content_id: str
    duration_seconds: int
    matching_activities: list[Activity]
    is_valid: bool
    rejection_reason: RejectionReason | None = None


def match_content_to_activities(
    content_id: str,
    duration_seconds: int,
    catalog: list[Activity] | None = None,
) -> ContentMatchResult:
    """Match content duration exactly against physical activity catalog per SPEC §5.2 & §9.6.

    Enforces rules:
    - Session duration equals content duration exactly ($D_{session} = D_{content}$).
    - Returns rejection_reason = "duration_out_of_range" if D < 300 or D > 10800.
    - Returns rejection_reason = "no_matching_activity" if D is globally valid (300 <= D <= 10800)
      but no activity catalog [min, max] range encloses D.
    """
    if catalog is None:
        catalog = PREDEFINED_ACTIVITIES

    # Check 1: Global duration boundaries
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

    # Check 2: Filter matching catalog activities
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
