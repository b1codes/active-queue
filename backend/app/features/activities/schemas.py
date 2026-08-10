from __future__ import annotations

from pydantic import BaseModel

from app.features.activities.models import Activity, TimeBlock


class ActivitySchema(BaseModel):
    """API response schema for an Activity per SPEC §9.5."""

    id: str
    name: str
    category: str
    tracker: str
    min_duration_seconds: int
    max_duration_seconds: int
    default_duration_seconds: int
    icon_name: str
    is_active: bool

    @classmethod
    def from_domain(cls, activity: Activity) -> ActivitySchema:
        """Convert Activity domain model to ActivitySchema response."""
        return cls(
            id=activity.id,
            name=activity.name,
            category=activity.category,
            tracker=activity.tracker,
            min_duration_seconds=activity.min_duration_seconds,
            max_duration_seconds=activity.max_duration_seconds,
            default_duration_seconds=activity.default_duration_seconds,
            icon_name=activity.icon_name,
            is_active=activity.is_active,
        )


class ActivityListResponse(BaseModel):
    """API response envelope content for GET /activities list."""

    activities: list[ActivitySchema]


class TimeBlockSchema(BaseModel):
    """API response schema for a TimeBlock per SPEC §5.3 & §9.5."""

    id: str
    label: str
    duration_seconds: int
    description: str

    @classmethod
    def from_domain(cls, time_block: TimeBlock) -> TimeBlockSchema:
        """Convert TimeBlock domain model to TimeBlockSchema response."""
        return cls(
            id=time_block.id,
            label=time_block.label,
            duration_seconds=time_block.duration_seconds,
            description=time_block.description,
        )


class TimeBlockListResponse(BaseModel):
    """API response envelope content for GET /activities/time-blocks list."""

    time_blocks: list[TimeBlockSchema]
