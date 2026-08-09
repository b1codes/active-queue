from __future__ import annotations

from typing import Any

from app.providers.base import ContentProvider


class YouTubeProvider(ContentProvider):
    """
    YouTube provider implementation.
    Placeholder for M2.
    """

    async def get_playlist_metadata(self, playlist_id: str) -> Any:
        pass

    async def fetch_playlist_items(self, playlist_id: str) -> Any:
        pass
