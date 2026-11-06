"""One contract for every ContentProvider (SPEC §8.4, §12.3; ClickUp 86bcxruxt).

The sync engine treats providers interchangeably, so FixtureProvider (dev, tests, the
emulator tier) and YouTubeProvider (production) must behave identically from its point
of view. Each test below runs once per provider through a harness. The YouTube harness
serves the recorded Data API v3 responses in tests/fixtures/youtube/, which
tests/contract/test_third_party_recorded.py holds to contracts/third_party/youtube/ and
the nightly live check holds to the real API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.providers.base import PlaylistMetadata, PlaylistPage, RawContentItem
from app.providers.fixture import UNAVAILABLE_EXTERNAL_IDS, FixtureProvider
from app.providers.youtube import API_BASE, YouTubeProvider

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from app.providers.base import ContentProvider

FIXTURES = Path(__file__).parents[2] / "fixtures" / "youtube"
MAX_PAGES = 100


def _fx(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@dataclass
class Harness:
    name: str
    provider: ContentProvider
    playlist_id: str
    raw_id: str  # a bare ID the provider accepts without a URL
    unavailable_ids: frozenset[str]
    quota: Callable[[], str]  # arrange quota exhaustion, return the playlist ID to call
    missing: Callable[[], str]  # arrange a missing playlist, return its ID


def _fixture_harness() -> Iterator[Harness]:
    yield Harness(
        name="fixture",
        provider=FixtureProvider(),
        playlist_id="fixture-small-playlist",
        raw_id="fixture-small-playlist",
        unavailable_ids=UNAVAILABLE_EXTERNAL_IDS,
        quota=lambda: "fixture-quota-exceeded",
        missing=lambda: "fixture-unavailable",
    )


def _youtube_harness() -> Iterator[Harness]:
    with respx.mock(assert_all_called=False) as router:

        def items(request: httpx.Request) -> httpx.Response:
            if request.url.params["playlistId"] == "PLmissing":
                return httpx.Response(404, json=_fx("error_playlist_not_found"))
            page = {None: "page1", "TOKEN_P2": "page2", "TOKEN_P3": "page3"}
            return httpx.Response(
                200, json=_fx(f"playlist_items_{page[request.url.params.get('pageToken')]}")
            )

        def videos(request: httpx.Request) -> httpx.Response:
            by_ids = {
                "vidA001,vidPriv1": "page1",
                "vidDel01,vidLive1": "page2",
                "vidB002": "page3",
            }
            return httpx.Response(200, json=_fx(f"videos_{by_ids[request.url.params['id']]}"))

        def playlists(request: httpx.Request) -> httpx.Response:
            if request.url.params["id"] == "PLmissing":
                return httpx.Response(200, json=_fx("playlists_empty"))
            return httpx.Response(200, json=_fx("playlists_ok"))

        playlists_route = router.get(f"{API_BASE}/playlists").mock(side_effect=playlists)
        items_route = router.get(f"{API_BASE}/playlistItems").mock(side_effect=items)
        router.get(f"{API_BASE}/videos").mock(side_effect=videos)

        def quota() -> str:
            exhausted = httpx.Response(403, json=_fx("error_quota"))
            playlists_route.mock(return_value=exhausted)
            items_route.mock(return_value=exhausted)
            return "PLfixture123"

        yield Harness(
            name="youtube",
            provider=YouTubeProvider(api_key="test-key"),
            playlist_id="PLfixture123",
            raw_id="PLfixture123",
            unavailable_ids=frozenset({"vidPriv1", "vidDel01"}),
            quota=quota,
            missing=lambda: "PLmissing",
        )


@pytest.fixture(params=["fixture", "youtube"])
def harness(request: pytest.FixtureRequest) -> Iterator[Harness]:
    factory = {"fixture": _fixture_harness, "youtube": _youtube_harness}[request.param]
    yield from factory()


async def _walk(h: Harness) -> tuple[list[RawContentItem], list[PlaylistPage]]:
    items: list[RawContentItem] = []
    pages: list[PlaylistPage] = []
    token: str | None = None
    for _ in range(MAX_PAGES):
        page = await h.provider.fetch_playlist_items(
            h.playlist_id, page_token=token, max_results=2
        )
        assert isinstance(page, PlaylistPage)
        pages.append(page)
        items += page.items
        token = page.next_page_token
        if token is None:
            return items, pages
    pytest.fail(f"{h.name}: pagination did not end within {MAX_PAGES} pages")


# --- validate_source_url -----------------------------------------------------------------


async def test_playlist_url_yields_its_list_id(harness: Harness) -> None:
    name, external_id = await harness.provider.validate_source_url(
        "https://www.youtube.com/playlist?list=PLcontract_1&si=share"
    )
    assert name
    assert external_id == "PLcontract_1"


async def test_bare_id_is_accepted_as_is(harness: Harness) -> None:
    _, external_id = await harness.provider.validate_source_url(f"  {harness.raw_id}  ")
    assert external_id == harness.raw_id


@pytest.mark.parametrize("text", ["", "   ", "not a playlist", "https://example.com/watch"])
async def test_unparseable_input_is_a_validation_error(harness: Harness, text: str) -> None:
    with pytest.raises(ValidationError) as exc:
        await harness.provider.validate_source_url(text)
    assert exc.value.code == "SOURCE_URL_UNPARSEABLE"


# --- get_playlist_metadata ---------------------------------------------------------------


async def test_metadata_shape(harness: Harness) -> None:
    meta = await harness.provider.get_playlist_metadata(harness.playlist_id)
    assert isinstance(meta, PlaylistMetadata)
    assert meta.source_id == harness.playlist_id
    assert meta.title.strip()
    assert meta.item_count is None or meta.item_count >= 0
    assert meta.thumbnail_url is None or meta.thumbnail_url.startswith("https://")


# --- fetch_playlist_items ----------------------------------------------------------------


async def test_full_walk_terminates_without_duplicates(harness: Harness) -> None:
    items, pages = await _walk(harness)
    ids = [i.external_id for i in items]
    assert ids, f"{harness.name}: walk returned no items"
    assert len(ids) == len(set(ids)), f"{harness.name}: duplicate items across pages"
    totals = {p.total_results for p in pages}
    assert len(totals) == 1, "total_results must be stable across pages"
    total = totals.pop()
    assert total is None or len(ids) <= total


async def test_items_are_well_formed(harness: Harness) -> None:
    items, _ = await _walk(harness)
    for item in items:
        assert item.external_id.strip()
        assert item.title.strip()
        assert item.duration_seconds >= 0  # 0 = live/upcoming; the matcher rejects it
        assert item.published_at.tzinfo is not None
        assert item.video_url in (None, f"https://www.youtube.com/watch?v={item.external_id}")
        assert item.thumbnail_url is None or item.thumbnail_url.startswith("https://")


async def test_unavailable_videos_are_dropped(harness: Harness) -> None:
    items, _ = await _walk(harness)
    assert not {i.external_id for i in items} & harness.unavailable_ids


# --- error mapping -----------------------------------------------------------------------


async def test_quota_exhaustion_is_provider_quota_exceeded(harness: Harness) -> None:
    playlist = harness.quota()
    calls = (
        harness.provider.get_playlist_metadata(playlist),
        harness.provider.fetch_playlist_items(playlist),
    )
    for call in calls:
        with pytest.raises(ProviderError) as exc:
            await call
        assert exc.value.code == "PROVIDER_QUOTA_EXCEEDED"
        assert exc.value.status_code == 503


async def test_missing_playlist_is_source_not_found(harness: Harness) -> None:
    playlist = harness.missing()
    for call in (
        harness.provider.get_playlist_metadata(playlist),
        harness.provider.fetch_playlist_items(playlist),
    ):
        with pytest.raises(NotFoundError) as exc:
            await call
        assert exc.value.code == "SOURCE_NOT_FOUND"
