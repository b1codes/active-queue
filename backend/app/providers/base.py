from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, field_validator

from app.core.errors import ValidationError
from app.core.sanitizer import sanitize_text, sanitize_url


# Provider name <-> prefix mapping per SPEC §4.1
PROVIDER_PREFIXES: dict[str, str] = {
    "youtube": "yt",
    "spotify": "sp",
    "fixture": "fx",
}

PREFIX_TO_PROVIDER: dict[str, str] = {v: k for k, v in PROVIDER_PREFIXES.items()}


def format_content_id(provider: str, external_id: str) -> str:
    """Format namespaced content ID per SPEC §4.1 (e.g. yt:<videoId>, fx:<itemId>).

    >>> format_content_id("youtube", "dQw4w9WgXcQ")
    'yt:dQw4w9WgXcQ'
    """
    prefix = PROVIDER_PREFIXES.get(provider.lower(), provider.lower())
    return f"{prefix}:{external_id}"


def parse_content_id(content_id: str) -> tuple[str, str]:
    """Parse namespaced content ID into (provider_name, external_id) per SPEC §4.1.

    >>> parse_content_id("yt:dQw4w9WgXcQ")
    ('youtube', 'dQw4w9WgXcQ')
    """
    if ":" not in content_id:
        raise ValidationError(
            code="SOURCE_URL_UNPARSEABLE",
            message=f"Invalid namespaced content_id format '{content_id}'. Must be 'prefix:external_id'.",
        )

    prefix, external_id = content_id.split(":", 1)
    if not prefix or not external_id:
        raise ValidationError(
            code="SOURCE_URL_UNPARSEABLE",
            message=f"Invalid namespaced content_id format '{content_id}'. Prefix and external_id must not be empty.",
        )

    provider = PREFIX_TO_PROVIDER.get(prefix.lower(), prefix.lower())
    return provider, external_id


class PlaylistMetadata(BaseModel):
    """Metadata for a content playlist or channel per SPEC §8.4."""

    source_id: str
    title: str
    description: str | None = None
    item_count: int | None = None
    thumbnail_url: str | None = None

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return sanitize_text(v, max_length=500) or v.strip()

    @field_validator("description")
    @classmethod
    def sanitize_desc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_text(v, max_length=5000)

    @field_validator("thumbnail_url")
    @classmethod
    def sanitize_thumb(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_url(v)


class RawContentItem(BaseModel):
    """Raw item fetched from a content provider per SPEC §8.4."""

    external_id: str
    title: str
    duration_seconds: int
    published_at: datetime
    thumbnail_url: str | None = None
    video_url: str | None = None

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return sanitize_text(v, max_length=500) or v.strip()

    @field_validator("thumbnail_url", "video_url")
    @classmethod
    def sanitize_media_urls(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_url(v)


class PlaylistPage(BaseModel):
    """A paginated page of items fetched from a content provider per SPEC §8.4."""

    items: list[RawContentItem]
    next_page_token: str | None = None
    total_results: int | None = None


class ContentProvider(Protocol):
    """Protocol for content providers per SPEC §8.1 & §8.4.

    Nothing outside app/providers/ may reference YouTube by name, and nothing
    downstream of the namespace parse may assume a provider.
    """

    async def validate_source_url(self, url: str) -> tuple[str, str]:
        """Validate URL format and extract (provider_name, external_source_id)."""
        ...

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        """Fetch playlist or channel metadata."""
        ...

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
    ) -> PlaylistPage:
        """Fetch a page of raw content items."""
        ...
