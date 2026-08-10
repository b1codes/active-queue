from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.content.models import Source


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
    status: str  # "active" | "syncing" | "error"
    items_synced: int
    has_more: bool
    next_page_token: str | None = None
    message: str | None = None
