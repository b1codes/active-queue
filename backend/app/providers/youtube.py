from __future__ import annotations

from app.providers.base import ContentProvider, PlaylistMetadata, PlaylistPage


class YouTubeProvider(ContentProvider):
    """YouTube provider implementation.

    Placeholder for M2 (YouTube Data API v3 provider).
    """

    async def validate_source_url(self, url: str) -> tuple[str, str]:
        raise NotImplementedError("YouTubeProvider will be implemented in M2 subtask")

    async def get_playlist_metadata(self, source_id: str) -> PlaylistMetadata:
        raise NotImplementedError("YouTubeProvider will be implemented in M2 subtask")

    async def fetch_playlist_items(
        self,
        source_id: str,
        page_token: str | None = None,
        max_results: int = 50,
    ) -> PlaylistPage:
        raise NotImplementedError("YouTubeProvider will be implemented in M2 subtask")
