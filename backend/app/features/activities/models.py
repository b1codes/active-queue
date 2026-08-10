from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Activity:
    """Domain model for a physical activity per SPEC §5.1 & §9.5.

    Min/max duration_seconds encode sane limits for the activity type,
    not a user preference.
    """

    id: str
    name: str
    category: str
    tracker: str
    min_duration_seconds: int
    max_duration_seconds: int
    default_duration_seconds: int
    icon_name: str
    is_active: bool = True


@dataclass(frozen=True)
class TimeBlock:
    """Domain model for a target time block option per SPEC §5.3."""

    id: str
    label: str
    duration_seconds: int
    description: str
