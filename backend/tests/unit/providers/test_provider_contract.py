from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.providers.base import ContentProvider, PlaylistMetadata, PlaylistPage
from app.providers.fixture import FixtureProvider
from app.providers.youtube import YouTubeProvider

_real_async_client = httpx.AsyncClient


def _mock_youtube_httpx_handler(request: httpx.Request) -> httpx.Response:
    """Mock handler for YouTube Data API v3 responses in contract tests."""
    url_str = str(request.url)
    if "playlists" in url_str:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "title": "Contract Test Playlist",
                            "description": "Playlist for provider contract verification",
                            "thumbnails": {"high": {"url": "https://img.youtube.com/thumb.jpg"}},
                        },
                        "contentDetails": {"itemCount": 25},
                    }
                ]
            },
        )
    if "playlistItems" in url_str:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "title": "Contract Test Video 1",
                            "publishedAt": "2026-01-01T00:00:00Z",
                            "resourceId": {"videoId": "contract_vid_1"},
                        },
                        "contentDetails": {"videoId": "contract_vid_1"},
                    }
                ],
                "nextPageToken": "token_page_2",
                "pageInfo": {"totalResults": 25},
            },
        )
    if "videos" in url_str:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "contract_vid_1",
                        "snippet": {
                            "title": "Contract Test Video 1",
                            "publishedAt": "2026-01-01T00:00:00Z",
                            "thumbnails": {"default": {"url": "https://img.youtube.com/v1.jpg"}},
                        },
                        "contentDetails": {"duration": "PT45M"},
                    }
                ]
            },
        )
    return httpx.Response(404, json={"error": "Not found"})


def _make_mock_async_client_factory(transport: httpx.MockTransport) -> Any:
    def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return _real_async_client(*args, **kwargs)

    return _factory


@pytest.fixture
def fixture_provider_instance() -> FixtureProvider:
    return FixtureProvider()


@pytest.fixture
def youtube_provider_instance() -> YouTubeProvider:
    return YouTubeProvider(api_key="test-api-key")


@pytest.mark.asyncio
async def test_provider_contract_validate_source_url(
    fixture_provider_instance: FixtureProvider,
    youtube_provider_instance: YouTubeProvider,
) -> None:
    """Both FixtureProvider and YouTubeProvider fulfill URL validation contract per SPEC §12.3."""
    providers: list[tuple[ContentProvider, str]] = [
        (fixture_provider_instance, "https://youtube.com/playlist?list=PLcontract_1"),
        (youtube_provider_instance, "https://youtube.com/playlist?list=PLcontract_1"),
    ]

    for provider, test_url in providers:
        provider_name, external_id = await provider.validate_source_url(test_url)
        assert isinstance(provider_name, str)
        assert len(provider_name) > 0
        assert external_id == "PLcontract_1"


@pytest.mark.asyncio
async def test_provider_contract_get_playlist_metadata(
    fixture_provider_instance: FixtureProvider,
    youtube_provider_instance: YouTubeProvider,
) -> None:
    """Both FixtureProvider and YouTubeProvider fulfill get_playlist_metadata contract per SPEC §12.3."""
    # Test FixtureProvider
    fx_meta = await fixture_provider_instance.get_playlist_metadata("PLcontract_1")
    assert isinstance(fx_meta, PlaylistMetadata)
    assert fx_meta.source_id == "PLcontract_1"
    assert isinstance(fx_meta.title, str)
    assert fx_meta.item_count is not None and fx_meta.item_count > 0

    # Test YouTubeProvider with httpx mock
    transport = httpx.MockTransport(_mock_youtube_httpx_handler)
    client_factory = _make_mock_async_client_factory(transport)
    with patch("httpx.AsyncClient", client_factory):
        yt_meta = await youtube_provider_instance.get_playlist_metadata("PLcontract_1")
        assert isinstance(yt_meta, PlaylistMetadata)
        assert yt_meta.source_id == "PLcontract_1"
        assert yt_meta.title == "Contract Test Playlist"
        assert yt_meta.item_count == 25


@pytest.mark.asyncio
async def test_provider_contract_fetch_playlist_items(
    fixture_provider_instance: FixtureProvider,
    youtube_provider_instance: YouTubeProvider,
) -> None:
    """Both FixtureProvider and YouTubeProvider fulfill fetch_playlist_items contract per SPEC §12.3."""
    # Test FixtureProvider
    fx_page = await fixture_provider_instance.fetch_playlist_items("PLcontract_1", max_results=10)
    assert isinstance(fx_page, PlaylistPage)
    assert len(fx_page.items) > 0
    first_fx_item = fx_page.items[0]
    assert isinstance(first_fx_item.external_id, str)
    assert isinstance(first_fx_item.title, str)
    assert isinstance(first_fx_item.duration_seconds, int)
    assert first_fx_item.duration_seconds >= 0

    # Test YouTubeProvider with httpx mock
    transport = httpx.MockTransport(_mock_youtube_httpx_handler)
    client_factory = _make_mock_async_client_factory(transport)
    with patch("httpx.AsyncClient", client_factory):
        yt_page = await youtube_provider_instance.fetch_playlist_items(
            "PLcontract_1", max_results=10
        )
        assert isinstance(yt_page, PlaylistPage)
        assert len(yt_page.items) == 1
        first_yt_item = yt_page.items[0]
        assert first_yt_item.external_id == "contract_vid_1"
        assert first_yt_item.title == "Contract Test Video 1"
        assert first_yt_item.duration_seconds == 2700  # PT45M = 2700s
        assert yt_page.next_page_token == "token_page_2"
