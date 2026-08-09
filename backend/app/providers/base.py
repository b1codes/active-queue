from __future__ import annotations

from typing import Any, Protocol


class ContentProvider(Protocol):
    """
    Protocol for content providers (e.g. YouTube, Fixture).
    Reference: SPEC §8.4
    """

    async def get_playlist_metadata(self, playlist_id: str) -> Any: ...

    async def fetch_playlist_items(self, playlist_id: str) -> Any: ...
