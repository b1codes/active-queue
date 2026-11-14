"""Nightly: the real YouTube Data API v3 still matches contracts/third_party/youtube/.

Quota (docs/deployment/youtube_api_quota_setup.md): every call below costs 1 unit, about
8 units a night out of the 10,000/day default. Needs YOUTUBE_API_KEY and
YOUTUBE_CONTRACT_PLAYLIST_ID (a stable public playlist with at least 2 videos).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.errors import NotFoundError
from app.providers.youtube import API_BASE, YouTubeProvider, parse_iso8601_duration
from tests.contract.test_third_party_recorded import errors_for
from tests.contract.thirdparty.conftest import require_env

BOGUS_PLAYLIST = "PLactivequeueContractCheckDoesNotExist0"
PAGE = 5


@pytest.fixture(scope="module")
def key() -> str:
    return require_env("YOUTUBE_API_KEY")


@pytest.fixture(scope="module")
def playlist() -> str:
    return require_env("YOUTUBE_CONTRACT_PLAYLIST_ID")


async def _get(endpoint: str, **params: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await client.get(f"{API_BASE}/{endpoint}", params=params)


def _assert_contract(schema: str, body: Any) -> None:
    errors = errors_for(f"youtube/{schema}", body)
    assert not errors, f"live {schema} response drifted from the contract:\n" + "\n".join(errors)


async def test_playlists_list(key: str, playlist: str) -> None:
    resp = await _get("playlists", part="snippet,contentDetails", id=playlist, key=key)
    assert resp.status_code == 200, resp.text
    _assert_contract("playlists.list", resp.json())
    assert len(resp.json()["items"]) == 1


async def test_playlist_items_and_videos_list(key: str, playlist: str) -> None:
    resp = await _get(
        "playlistItems",
        part="snippet,contentDetails",
        playlistId=playlist,
        maxResults=PAGE,
        key=key,
    )
    assert resp.status_code == 200, resp.text
    _assert_contract("playlistItems.list", resp.json())
    ids = [i["contentDetails"]["videoId"] for i in resp.json()["items"]]
    assert ids, "contract playlist is empty; pick one with public videos"

    videos = await _get("videos", part="contentDetails,snippet", id=",".join(ids), key=key)
    assert videos.status_code == 200, videos.text
    _assert_contract("videos.list", videos.json())
    for video in videos.json()["items"]:
        assert parse_iso8601_duration(video["contentDetails"]["duration"]) >= 0


async def test_missing_playlist_shapes_the_provider_relies_on(key: str) -> None:
    """playlists.list answers 200 + no items; playlistItems.list answers 404 playlistNotFound."""
    meta = await _get("playlists", part="snippet,contentDetails", id=BOGUS_PLAYLIST, key=key)
    assert meta.status_code == 200, meta.text
    assert meta.json()["items"] == []

    items = await _get("playlistItems", part="snippet", playlistId=BOGUS_PLAYLIST, key=key)
    assert items.status_code == 404, items.text
    _assert_contract("error", items.json())
    assert items.json()["error"]["errors"][0]["reason"] == "playlistNotFound"


async def test_provider_end_to_end(key: str, playlist: str) -> None:
    provider = YouTubeProvider(api_key=key)
    meta = await provider.get_playlist_metadata(playlist)
    assert meta.source_id == playlist
    assert meta.title.strip()

    page = await provider.fetch_playlist_items(playlist, max_results=PAGE)
    assert page.items
    for item in page.items:
        assert item.video_url == f"https://www.youtube.com/watch?v={item.external_id}"
        assert item.published_at.tzinfo is not None

    with pytest.raises(NotFoundError):
        await provider.fetch_playlist_items(BOGUS_PLAYLIST)
