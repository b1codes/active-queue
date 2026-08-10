from __future__ import annotations

from app.core.errors import NotFoundError, ValidationError
from app.features.activities.catalog import (
    get_activity_by_id,
    get_all_activities,
    get_all_time_blocks,
    validate_activity_duration,
)
from app.features.activities.models import Activity, TimeBlock


class ActivityService:
    """Business logic service for physical activity catalog and time blocks per SPEC §5.1, §5.3, & §9.5.

    Operates purely over static, version-controlled catalog structures.
    """

    def list_activities(self) -> list[Activity]:
        """Fetch all predefined physical activities."""
        return get_all_activities()

    def get_activity(self, activity_id: str) -> Activity:
        """Fetch a specific activity by ID or raise NotFoundError."""
        act = get_activity_by_id(activity_id)
        if not act:
            raise NotFoundError(
                code="ACTIVITY_NOT_FOUND",
                message=f"Activity '{activity_id}' not found in catalog",
            )
        return act

    def list_time_blocks(self) -> list[TimeBlock]:
        """Fetch all predefined time block options."""
        return get_all_time_blocks()

    def validate_duration(self, activity_id: str, duration_seconds: int) -> None:
        """Validate activity duration within sane catalog bounds or raise ValidationError."""
        act = self.get_activity(activity_id)
        if not validate_activity_duration(activity_id, duration_seconds):
            raise ValidationError(
                code="ACTIVITY_DURATION_MISMATCH",
                message=f"Duration {duration_seconds}s out of range [{act.min_duration_seconds}s, {act.max_duration_seconds}s] for activity '{act.name}'",
            )
