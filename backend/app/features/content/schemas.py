from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.content.models import Source


def format_duration_label(duration_seconds: int) -> str:
    """Format duration in seconds into human-readable label per SPEC §9.2.

    Examples:
    - 2712 -> "45m 12s"
    - 3665 -> "1h 1m 5s"
    - 3600 -> "1h 0m"
    - 120 -> "2m 0s"
    - 45 -> "45s"
    - 0 -> "0s"
    """
    if duration_seconds <= 0:
        return "0s"

    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m" if seconds == 0 else f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


class CreateSourceRequest(BaseModel):
    """Request payload for adding a content source per SPEC §9.3."""

    url_or_id: str = Field(
        ...,
        description="Pasted YouTube playlist/channel URL or raw playlist/channel ID",
        examples=["https://www.youtube.com/playlist?list=PL12345", "PL12345"],
    )


class SourceSchema(BaseModel):
    """API response schema for a content source per SPEC §9.3."""

    id: str
    user_id: str
    provider: str
    external_source_id: str
    title: str
    description: str | None = None
    item_count: int | None = None
    thumbnail_url: str | None = None
    status: str
    last_sync_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, source: Source) -> SourceSchema:
        """Convert Source domain model to SourceSchema API response."""
        return cls(
            id=source.id,
            user_id=source.user_id,
            provider=source.provider,
            external_source_id=source.external_source_id,
            title=source.title,
            description=source.description,
            item_count=source.item_count,
            thumbnail_url=source.thumbnail_url,
            status=source.status,
            last_sync_at=source.last_sync_at,
            created_at=source.created_at,
        )


class SourceListResponse(BaseModel):
    """API response payload for GET /sources list."""

    items: list[SourceSchema]


class SyncResponse(BaseModel):
    """API response payload for POST /sources/{source_id}/sync per SPEC §9.4."""

    source_id: str
    status: str
    items_synced: int
    has_more: bool
    next_page_token: str | None = None
    message: str | None = None


class FeedItemSchema(BaseModel):
    """API response schema for an enriched feed item per SPEC §9.2."""

    id: str
    content_id: str
    source_id: str
    title: str
    provider: str
    external_id: str
    duration_seconds: int
    duration_label: str
    published_at: datetime
    thumbnail_url: str | None = None
    video_url: str | None = None
    consumed: bool = False


class FeedResponse(BaseModel):
    """API response payload for GET /feed per SPEC §9.2.

    total_unconsumed is computed on first page only (cursor is None).
    """

    items: list[FeedItemSchema]
    next_cursor: str | None = None
    total_unconsumed: int | None = None
