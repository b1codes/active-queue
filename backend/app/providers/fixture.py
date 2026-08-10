from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.providers.base import (
    ContentProvider,
    PlaylistMetadata,
    PlaylistPage,
    RawContentItem,
)

# Pre-generated edge-case items
EDGE_CASE_ITEMS = {
    10: RawContentItem(
        external_id="vid_private_10",
        title="[Private video]",
        duration_seconds=0,
        published_at=datetime(2025, 1, 10, 12, 0, tzinfo=UTC),
        thumbnail_url=None,
        video_url=None,
    ),
    20: RawContentItem(
        external_id="vid_deleted_20",
        title="[Deleted video]",
        duration_seconds=0,
        published_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
        thumbnail_url=None,
        video_url=None,
    ),
    30: RawContentItem(
        external_id="vid_livestream_30",
        title="Live 24/7 Lo-Fi Beats Broadcast",
        duration_seconds=0,  # Live stream duration P0D
        published_at=datetime(2025, 1, 30, 12, 0, tzinfo=UTC),
        thumbnail_url="https://img.youtube.com/vi/vid_livestream_30/hqdefault.jpg",
        video_url="https://www.youtube.com/watch?v=vid_livestream_30",
    ),
}


def _generate_fixture_items(count: int) -> list[RawContentItem]:
    """Generate deterministically reproducible raw content items for testing."""
    items: list[RawContentItem] = []
    base_time = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)

    for idx in range(count):
        if idx in EDGE_CASE_ITEMS:
            items.append(EDGE_CASE_ITEMS[idx])
            continue

        ext_id = f"fx_vid_{idx + 1:04d}"
        # Varying durations: 5 mins, 15 mins, 30 mins, 45 mins, 60 mins
        duration = 300 + (idx % 5) * 600
        pub_time = base_time + timedelta(hours=idx)

        items.append(
            RawContentItem(
                external_id=ext_id,
                title=f"Fixture Workout Video #{idx + 1} — High Intensity Cardio",
                duration_seconds=duration,
                published_at=pub_time,
                thumbnail_url=f"https://img.youtube.com/vi/{ext_id}/hqdefault.jpg",
                video_url=f"https://www.youtube.com/watch?v={ext_id}",
            )
        )
    return items


# Corpus registry
LARGE_PLAYLIST_ITEMS = _generate_fixture_items(
    1200
)  # 1,200 items to cross 250-item chunk boundary
SMALL_PLAYLIST_ITEMS = _generate_fixture_items(15)


class FixtureProvider(ContentProvider):
    """Fixture content provider for offline development & integration testing per SPEC §8.4.

    Allows running the full ActiveQueue application with zero GCP dependency, zero API keys,
    and zero network overhead.
    """

    async def validate_source_url(self, url: str) -> tuple[str, str]:
        """Validate URL and extract (provider_name, source_id).

        Supports:
        - https://www.youtube.com/playlist?list=PL12345
        - fixture:playlist-id
        - Direct source IDs
        """
        url = url.strip()
        if not url:
            raise ValidationError(
                code="SOURCE_URL_UNPARSEABLE",
                message="Source URL cannot be empty",
            )

        if url.startswith("fixture:"):
            source_id = url.split("fixture:", 1)[1]
            return "fixture", source_id

        # YouTube playlist URL regex pattern
        match = re.search(r"list=([A-Za-z0-9_-]+)", url)
        if match:
            return "fixture", match.group(1)

        if url in (
            "fixture-large-playlist",
            "fixture-small-playlist",
            "fixture-empty-playlist",
            "fixture-quota-exceeded",
            "fixture-unavailable",
        ):
            return "fixture", url

        raise ValidationError(
            code="SOURCE_URL_UNPARSEABLE",
            message=f"Unable to parse playlist ID from URL '{url}'",
        )

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        """Fetch playlist metadata for fixture source ID."""
        if source_id == "fixture-quota-exceeded":
            raise ProviderError(
                code="PROVIDER_QUOTA_EXCEEDED",
                message="YouTube API quota exceeded (fixture test trigger)",
            )

        if source_id == "fixture-unavailable":
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message=f"Source playlist {source_id} not found or private",
            )

        if source_id == "fixture-small-playlist":
            return PlaylistMetadata(
                source_id=source_id,
                title="Small Fixture Fitness Playlist",
                description="A small test playlist with 15 workout videos",
                item_count=15,
                thumbnail_url="https://img.youtube.com/vi/fx_vid_0001/hqdefault.jpg",
            )

        if source_id == "fixture-empty-playlist":
            return PlaylistMetadata(
                source_id=source_id,
                title="Empty Fixture Playlist",
                description="An empty test playlist",
                item_count=0,
                thumbnail_url=None,
            )

        # Default to large playlist (1,200 items)
        return PlaylistMetadata(
            source_id=source_id,
            title="Large Fixture Fitness Playlist (1,200 videos)",
            description="A comprehensive fixture corpus playlist for testing chunked resumable sync",
            item_count=1200,
            thumbnail_url="https://img.youtube.com/vi/fx_vid_0001/hqdefault.jpg",
        )

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
    ) -> PlaylistPage:
        """Fetch paginated page of playlist items."""
        if source_id == "fixture-quota-exceeded":
            raise ProviderError(
                code="PROVIDER_QUOTA_EXCEEDED",
                message="YouTube API quota exceeded (fixture test trigger)",
            )

        if source_id == "fixture-unavailable":
            raise NotFoundError(
                code="SOURCE_NOT_FOUND",
                message=f"Source playlist {source_id} not found or private",
            )

        if source_id == "fixture-empty-playlist":
            return PlaylistPage(items=[], next_page_token=None, total_results=0)

        items_corpus = (
            SMALL_PLAYLIST_ITEMS if source_id == "fixture-small-playlist" else LARGE_PLAYLIST_ITEMS
        )

        offset = 0
        if page_token:
            try:
                offset = int(page_token)
            except ValueError:
                offset = 0

        end_offset = min(offset + max_results, len(items_corpus))
        page_items = items_corpus[offset:end_offset]

        next_token = str(end_offset) if end_offset < len(items_corpus) else None

        return PlaylistPage(
            items=page_items,
            next_page_token=next_token,
            total_results=len(items_corpus),
        )
