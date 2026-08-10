from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import ProviderError, ValidationError
from app.providers.youtube import YouTubeProvider, parse_iso8601_duration


def test_parse_iso8601_duration_test_cases() -> None:
    """parse_iso8601_duration accurately parses ISO-8601 duration formats per SPEC §8.4."""
    assert parse_iso8601_duration("PT45M") == 2700
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("PT10S") == 10
    assert parse_iso8601_duration("P0D") == 0  # Live stream
    assert parse_iso8601_duration("PT1H") == 3600
    assert parse_iso8601_duration("P1D") == 86400
    assert parse_iso8601_duration(None) == 0
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration("INVALID") == 0


@pytest.mark.asyncio
async def test_youtube_provider_validate_source_url() -> None:
    """YouTubeProvider.validate_source_url extracts source IDs from playlist/channel URLs."""
    provider = YouTubeProvider(api_key="test-key")

    res1 = await provider.validate_source_url("https://www.youtube.com/playlist?list=PL123456789")
    assert res1 == ("youtube", "PL123456789")

    res2 = await provider.validate_source_url("https://www.youtube.com/channel/UCabcdef123")
    assert res2 == ("youtube", "UCabcdef123")

    res3 = await provider.validate_source_url("PL999999999")
    assert res3 == ("youtube", "PL999999999")

    with pytest.raises(ValidationError) as exc_info:
        await provider.validate_source_url("https://example.com/not-youtube")
    assert exc_info.value.code == "SOURCE_URL_UNPARSEABLE"


@pytest.mark.asyncio
async def test_youtube_provider_get_playlist_metadata_success() -> None:
    """YouTubeProvider.get_playlist_metadata fetches and parses metadata."""
    provider = YouTubeProvider(api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "snippet": {
                    "title": "My Fitness Playlist",
                    "description": "Fitness workout videos",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/high.jpg"}},
                },
                "contentDetails": {"itemCount": 42},
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        meta = await provider.get_playlist_metadata("PL123")

    assert meta.source_id == "PL123"
    assert meta.title == "My Fitness Playlist"
    assert meta.item_count == 42
    assert meta.thumbnail_url == "https://img.youtube.com/high.jpg"


@pytest.mark.asyncio
async def test_youtube_provider_quota_exceeded() -> None:
    """YouTubeProvider raises PROVIDER_QUOTA_EXCEEDED on 403 quotaExceeded."""
    provider = YouTubeProvider(api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {
        "error": {
            "errors": [{"reason": "quotaExceeded", "message": "Quota exceeded"}],
            "message": "Quota exceeded",
        }
    }

    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        pytest.raises(ProviderError) as exc_info,
    ):
        await provider.get_playlist_metadata("PL123")

    assert exc_info.value.code == "PROVIDER_QUOTA_EXCEEDED"
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_youtube_provider_fetch_playlist_items_with_silent_private_video() -> None:
    """YouTubeProvider handles the silent case where private/deleted video is absent from videos.list."""
    provider = YouTubeProvider(api_key="test-key")

    # playlistItems.list returns 2 items (vid1 and vid2_private)
    mock_items_resp = MagicMock()
    mock_items_resp.status_code = 200
    mock_items_resp.json.return_value = {
        "nextPageToken": "token_next",
        "pageInfo": {"totalResults": 2},
        "items": [
            {
                "snippet": {
                    "title": "Public Video 1",
                    "resourceId": {"videoId": "vid1"},
                    "publishedAt": "2025-01-01T00:00:00Z",
                }
            },
            {
                "snippet": {
                    "title": "[Private Video]",
                    "resourceId": {"videoId": "vid2_private"},
                    "publishedAt": "2025-01-02T00:00:00Z",
                }
            },
        ],
    }

    # videos.list returns details ONLY for vid1 (vid2_private is silently absent per SPEC §8.3)
    mock_videos_resp = MagicMock()
    mock_videos_resp.status_code = 200
    mock_videos_resp.json.return_value = {
        "items": [
            {
                "id": "vid1",
                "snippet": {"title": "Public Video 1", "publishedAt": "2025-01-01T00:00:00Z"},
                "contentDetails": {"duration": "PT15M"},
            }
        ]
    }

    with patch("httpx.AsyncClient.get", side_effect=[mock_items_resp, mock_videos_resp]):
        page = await provider.fetch_playlist_items("PL123")

    assert len(page.items) == 2
    assert page.next_page_token == "token_next"
    assert page.total_results == 2

    # Public video
    assert page.items[0].external_id == "vid1"
    assert page.items[0].duration_seconds == 900  # 15 mins

    # Silent missing private video
    assert page.items[1].external_id == "vid2_private"
    assert page.items[1].duration_seconds == 0
