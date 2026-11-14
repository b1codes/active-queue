"""YouTubeProvider against respx-mocked Data API v3 responses (SPEC §12.3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.core.errors import NotFoundError, ProviderError
from app.providers.youtube import API_BASE, YouTubeProvider

FIXTURES = Path(__file__).parents[2] / "fixtures" / "youtube"


def fx(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def yt() -> YouTubeProvider:
    return YouTubeProvider(api_key="test-key")


@respx.mock
async def test_metadata_parses_title_count_and_best_thumbnail(yt: YouTubeProvider) -> None:
    route = respx.get(f"{API_BASE}/playlists").respond(200, json=fx("playlists_ok"))
    meta = await yt.get_playlist_metadata("PLfixture123")
    assert meta.title == "Morning Run Podcasts"
    assert meta.item_count == 3
    assert meta.thumbnail_url == "https://i.ytimg.com/vi/aaa/hqdefault.jpg"
    sent = route.calls.last.request.url.params
    assert sent["id"] == "PLfixture123"
    assert sent["part"] == "snippet,contentDetails"
    assert sent["key"] == "test-key"


@respx.mock
async def test_metadata_empty_items_is_not_found(yt: YouTubeProvider) -> None:
    respx.get(f"{API_BASE}/playlists").respond(200, json=fx("playlists_empty"))
    with pytest.raises(NotFoundError) as exc:
        await yt.get_playlist_metadata("PLgone")
    assert exc.value.code == "SOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (403, "error_quota", "PROVIDER_QUOTA_EXCEEDED"),
        (403, "error_forbidden", "PROVIDER_UNAVAILABLE"),
        (500, None, "PROVIDER_UNAVAILABLE"),
        (503, None, "PROVIDER_UNAVAILABLE"),
    ],
)
@respx.mock
async def test_metadata_error_mapping(
    yt: YouTubeProvider, status: int, body: str | None, code: str
) -> None:
    respx.get(f"{API_BASE}/playlists").respond(
        status, json=fx(body) if body else None, text=None if body else "<html>oops</html>"
    )
    with pytest.raises(ProviderError) as exc:
        await yt.get_playlist_metadata("PL1")
    assert exc.value.code == code
    assert exc.value.status_code == 503


@respx.mock
async def test_daily_limit_exceeded_is_quota(yt: YouTubeProvider) -> None:
    body = fx("error_quota")
    body["error"]["errors"][0]["reason"] = "dailyLimitExceeded"
    respx.get(f"{API_BASE}/playlists").respond(403, json=body)
    with pytest.raises(ProviderError) as exc:
        await yt.get_playlist_metadata("PL1")
    assert exc.value.code == "PROVIDER_QUOTA_EXCEEDED"


@pytest.mark.parametrize(
    "error", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("c")]
)
@respx.mock
async def test_transport_failures_are_provider_unavailable(
    yt: YouTubeProvider, error: Exception
) -> None:
    respx.get(f"{API_BASE}/playlists").mock(side_effect=error)
    with pytest.raises(ProviderError) as exc:
        await yt.get_playlist_metadata("PL1")
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


async def test_missing_api_key_is_provider_unavailable() -> None:
    provider = YouTubeProvider(api_key=None)
    provider._api_key = None
    for call in (
        provider.get_playlist_metadata("PL1"),
        provider.fetch_playlist_items("PL1"),
    ):
        with pytest.raises(ProviderError) as exc:
            await call
        assert exc.value.code == "PROVIDER_UNAVAILABLE"


@respx.mock
async def test_three_page_walk_skips_private_and_deleted_keeps_live(
    yt: YouTubeProvider,
) -> None:
    def items_route(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        page = {None: "page1", "TOKEN_P2": "page2", "TOKEN_P3": "page3"}[token]
        return httpx.Response(200, json=fx(f"playlist_items_{page}"))

    def videos_route(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"]
        page = {"vidA001,vidPriv1": "page1", "vidDel01,vidLive1": "page2", "vidB002": "page3"}
        return httpx.Response(200, json=fx(f"videos_{page[ids]}"))

    respx.get(f"{API_BASE}/playlistItems").mock(side_effect=items_route)
    respx.get(f"{API_BASE}/videos").mock(side_effect=videos_route)

    collected = []
    token: str | None = None
    for _ in range(5):
        page = await yt.fetch_playlist_items("PLfixture123", page_token=token, max_results=2)
        collected += page.items
        assert page.total_results == 5
        token = page.next_page_token
        if token is None:
            break

    assert [i.external_id for i in collected] == ["vidA001", "vidLive1", "vidB002"]
    by_id = {i.external_id: i for i in collected}
    assert by_id["vidA001"].duration_seconds == 2712
    assert by_id["vidA001"].published_at == datetime(2025, 1, 1, 8, tzinfo=UTC)
    assert by_id["vidA001"].thumbnail_url == "https://i.ytimg.com/vi/vidA001/hqdefault.jpg"
    assert by_id["vidLive1"].duration_seconds == 0  # P0D live stream
    assert by_id["vidB002"].duration_seconds == 3723


@respx.mock
async def test_videos_list_failure_raises_instead_of_dropping_the_page(
    yt: YouTubeProvider,
) -> None:
    """A transient videos.list 5xx must not look like 'every video went private'."""
    respx.get(f"{API_BASE}/playlistItems").respond(200, json=fx("playlist_items_page1"))
    respx.get(f"{API_BASE}/videos").respond(500, text="backend error")
    with pytest.raises(ProviderError) as exc:
        await yt.fetch_playlist_items("PLfixture123")
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


@respx.mock
async def test_playlist_items_not_found_and_quota(yt: YouTubeProvider) -> None:
    route = respx.get(f"{API_BASE}/playlistItems")
    route.respond(404, json=fx("error_playlist_not_found"))
    with pytest.raises(NotFoundError):
        await yt.fetch_playlist_items("PLgone")
    route.respond(403, json=fx("error_quota"))
    with pytest.raises(ProviderError) as exc:
        await yt.fetch_playlist_items("PLgone")
    assert exc.value.code == "PROVIDER_QUOTA_EXCEEDED"


@respx.mock
async def test_page_with_no_video_ids_skips_videos_call(yt: YouTubeProvider) -> None:
    respx.get(f"{API_BASE}/playlistItems").respond(
        200, json={"items": [{"snippet": {"title": "broken"}}], "nextPageToken": "N"}
    )
    videos = respx.get(f"{API_BASE}/videos")
    page = await yt.fetch_playlist_items("PL1")
    assert page.items == []
    assert page.next_page_token == "N"
    assert not videos.called


@respx.mock
async def test_bad_timestamps_and_missing_thumbnails_are_stable(yt: YouTubeProvider) -> None:
    respx.get(f"{API_BASE}/playlistItems").respond(
        200, json={"items": [{"contentDetails": {"videoId": "v1"}, "snippet": {}}]}
    )
    respx.get(f"{API_BASE}/videos").respond(
        200,
        json={
            "items": [
                {
                    "id": "v1",
                    "snippet": {"publishedAt": "not-a-date"},
                    "contentDetails": {"duration": "PT10M"},
                }
            ]
        },
    )
    first = (await yt.fetch_playlist_items("PL1")).items[0]
    second = (await yt.fetch_playlist_items("PL1")).items[0]
    # Same fallback every sync, so the item never jumps to the top of the feed.
    assert first.published_at == second.published_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert first.thumbnail_url is None
    assert first.title == "Untitled Video"


@respx.mock
async def test_duplicate_video_ids_in_a_page_are_collapsed(yt: YouTubeProvider) -> None:
    item = {"snippet": {"resourceId": {"videoId": "dup"}, "title": "t"}}
    respx.get(f"{API_BASE}/playlistItems").respond(200, json={"items": [item, item]})
    vids = respx.get(f"{API_BASE}/videos").respond(
        200, json={"items": [{"id": "dup", "contentDetails": {"duration": "PT5M"}}]}
    )
    page = await yt.fetch_playlist_items("PL1")
    assert [i.external_id for i in page.items] == ["dup"]
    assert vids.calls.last.request.url.params["id"] == "dup"


@respx.mock
async def test_error_body_that_is_not_json(yt: YouTubeProvider) -> None:
    respx.get(f"{API_BASE}/playlists").respond(403, text="<html>forbidden</html>")
    with pytest.raises(ProviderError) as exc:
        await yt.get_playlist_metadata("PL1")
    assert exc.value.code == "PROVIDER_UNAVAILABLE"
