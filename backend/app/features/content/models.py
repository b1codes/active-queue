from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ContentCacheItem(BaseModel):
    """Shared content cache document model for content_cache/{contentId} per SPEC §4.6.

    Immutable metadata shared across all users for a given content item.
    """

    content_id: str  # e.g. "yt:dQw4w9WgXcQ" or "fx:fx_vid_0001"
    provider: str  # "youtube" | "fixture"
    external_id: str
    title: str
    duration_seconds: int
    published_at: datetime
    thumbnail_url: str | None = None
    video_url: str | None = None
    is_available: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_firestore(self) -> dict[str, Any]:
        """Convert model to Firestore document dict."""
        return {
            "content_id": self.content_id,
            "provider": self.provider,
            "external_id": self.external_id,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "published_at": self.published_at,
            "thumbnail_url": self.thumbnail_url,
            "video_url": self.video_url,
            "is_available": self.is_available,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> ContentCacheItem:
        """Construct model from Firestore document dict."""
        return cls(
            content_id=data.get("content_id", ""),
            provider=data.get("provider", "fixture"),
            external_id=data.get("external_id", ""),
            title=data.get("title", ""),
            duration_seconds=int(data.get("duration_seconds", 0)),
            published_at=data.get("published_at") or datetime.now(UTC),
            thumbnail_url=data.get("thumbnail_url"),
            video_url=data.get("video_url"),
            is_available=bool(data.get("is_available", True)),
            created_at=data.get("created_at") or datetime.now(UTC),
            updated_at=data.get("updated_at") or datetime.now(UTC),
        )


class FeedItem(BaseModel):
    """User-specific feed document model for feed_items/{userId}_{contentId} per SPEC §4.7.

    Deterministic composite doc ID {user_id}_{content_id} guarantees sync idempotency.
    consumed boolean exists because Firestore cannot efficiently express "not in this array".
    """

    id: str  # "{user_id}_{content_id}"
    user_id: str
    content_id: str
    source_id: str
    published_at: datetime
    duration_seconds: int
    consumed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_firestore(self) -> dict[str, Any]:
        """Convert model to Firestore document dict."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_id": self.content_id,
            "source_id": self.source_id,
            "published_at": self.published_at,
            "duration_seconds": self.duration_seconds,
            "consumed": self.consumed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> FeedItem:
        """Construct model from Firestore document dict."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", ""),
            content_id=data.get("content_id", ""),
            source_id=data.get("source_id", ""),
            published_at=data.get("published_at") or datetime.now(UTC),
            duration_seconds=int(data.get("duration_seconds", 0)),
            consumed=bool(data.get("consumed", False)),
            created_at=data.get("created_at") or datetime.now(UTC),
            updated_at=data.get("updated_at") or datetime.now(UTC),
        )
