"""What a playlist sync costs: YouTube quota units, Firestore writes and time (SPEC §8.2, §8.3).

YouTube's 10,000 units a day are shared by every user of the app, which makes quota the
hardest scaling limit in v1. These tests run the real YouTubeProvider and sync engine on
the emulators against a fake Data API that serves playlists of any size and counts the
units each endpoint is billed. They hold each scenario in SPEC §8.3's cost table to its
budget, at the 5,000-item cap:

| Scenario                         | SPEC units | Budget here          |
|----------------------------------|-----------:|----------------------|
| cold (nothing cached)            |       ~201 | 1 + 2 per page       |
| warm (another user synced it)    |       ~101 | 1 + 1 per page       |
| start inside the 15-minute window|          0 | 0                    |
| preflight says unchanged         |          1 | 1                    |
| a 6,000-item playlist            |  capped    | stops at 5,000 items |
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx
from google.cloud.firestore_v1 import FieldFilter

from app.core.config import settings
from app.middleware.ratelimit import _limiter
from app.providers.youtube import API_BASE
from tests.firestore_meter import FirestoreMeter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

PLAYLIST = "PLperfPlaylist000000000000000001"
PAGE = 50
CAP = 5000
# Wall-clock budget for walking 5,000 items against the emulator (CI runners included).
COLD_SYNC_SECONDS = 60.0


class FakeYouTube:
    """Data API v3 playlists/playlistItems/videos, billed 1 unit per call (SPEC §8.3)."""

    def __init__(self, size: int) -> None:
        self.video_ids = [f"vid{i:08d}" for i in range(size)]
        self.units: Counter[str] = Counter()
        self.detailed: list[str] = []  # every ID videos.list was asked for

    def grow(self, n: int) -> None:
        start = len(self.video_ids)
        self.video_ids += [f"vid{i:08d}" for i in range(start, start + n)]

    @property
    def total_units(self) -> int:
        return sum(self.units.values())

    def reset(self) -> None:
        self.units.clear()
        self.detailed.clear()

    def playlists(self, request: httpx.Request) -> httpx.Response:
        self.units["playlists.list"] += 1
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {"title": "Perf playlist", "thumbnails": {}},
                        "contentDetails": {"itemCount": len(self.video_ids)},
                    }
                ]
            },
        )

    def playlist_items(self, request: httpx.Request) -> httpx.Response:
        self.units["playlistItems.list"] += 1
        offset = int(request.url.params.get("pageToken") or 0)
        page = self.video_ids[offset : offset + PAGE]
        body: dict[str, Any] = {
            "items": [
                {
                    "snippet": {
                        "title": f"Video {vid}",
                        "publishedAt": "2025-01-01T00:00:00Z",
                        "resourceId": {"videoId": vid},
                    },
                    "contentDetails": {"videoId": vid},
                }
                for vid in page
            ],
            "pageInfo": {"totalResults": len(self.video_ids)},
        }
        if offset + PAGE < len(self.video_ids):
            body["nextPageToken"] = str(offset + PAGE)
        return httpx.Response(200, json=body)

    def videos(self, request: httpx.Request) -> httpx.Response:
        self.units["videos.list"] += 1
        ids = request.url.params["id"].split(",")
        assert len(ids) <= PAGE
        self.detailed += ids
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": vid,
                        "snippet": {
                            "title": f"Video {vid}",
                            "publishedAt": "2025-01-01T00:00:00Z",
                        },
                        "contentDetails": {"duration": "PT15M"},
                    }
                    for vid in ids
                ]
            },
        )


@pytest.fixture
def youtube(db: FirestoreAsyncClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeYouTube]:
    monkeypatch.setattr(settings, "content_provider", "youtube")
    monkeypatch.setattr(settings, "youtube_api_key", "perf-test-key")
    fake = FakeYouTube(CAP)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{API_BASE}/playlists").mock(side_effect=fake.playlists)
        mock.get(f"{API_BASE}/playlistItems").mock(side_effect=fake.playlist_items)
        mock.get(f"{API_BASE}/videos").mock(side_effect=fake.videos)
        mock.route(host="127.0.0.1").pass_through()  # the Auth emulator
        yield fake


@pytest.fixture
def meter(db: FirestoreAsyncClient, monkeypatch: pytest.MonkeyPatch) -> FirestoreMeter:
    m = FirestoreMeter()
    m.install(monkeypatch)
    return m


async def _add(api: AsyncClient, user: EmulatorUser) -> str:
    resp = await api.post(
        "/api/v1/sources",
        json={"url_or_id": f"https://www.youtube.com/playlist?list={PLAYLIST}"},
        headers=user.headers,
    )
    assert resp.status_code == 201, resp.text
    source_id: str = resp.json()["data"]["id"]
    return source_id


async def _sync(api: AsyncClient, user: EmulatorUser, source_id: str) -> list[dict[str, Any]]:
    """Run the app's sync loop to completion; return each chunk's response."""
    chunks: list[dict[str, Any]] = []
    for _ in range(40):  # the app's SPEC §9.4 loop guard
        _limiter.reset()
        resp = await api.post(f"/api/v1/sources/{source_id}/sync", headers=user.headers)
        assert resp.status_code == 200, resp.text
        chunks.append(resp.json()["data"])
        if not chunks[-1]["has_more"]:
            return chunks
    pytest.fail("sync did not finish within the app's 40-chunk guard")


async def _age(db: FirestoreAsyncClient, source_id: str, **ago: float) -> None:
    """Pretend the source's last completed sync happened `ago` in the past."""
    last = datetime.now(UTC) - timedelta(**ago)
    await db.collection("sources").document(source_id).update({"last_sync_at": last})


async def _feed_size(db: FirestoreAsyncClient, user: EmulatorUser) -> int:
    query = (
        db.collection("feed_items").where(filter=FieldFilter("user_id", "==", user.uid)).count()
    )
    result = await query.get()
    return int(result[0][0].value)


def _pages(items: int) -> int:
    return -(-items // PAGE)


async def test_cold_sync_of_the_largest_playlist(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    meter: FirestoreMeter,
    make_user: Callable[..., EmulatorUser],
) -> None:
    alice = make_user()
    source_id = await _add(api, alice)
    youtube.reset()
    meter.reset()

    started = time.monotonic()
    chunks = await _sync(api, alice, source_id)
    elapsed = time.monotonic() - started

    pages = _pages(CAP)
    assert youtube.total_units <= 1 + 2 * pages, youtube.units
    # SPEC §8.2: a chunk is at most 5 pages, so at most 10 units per request.
    assert len(chunks) == -(-pages // settings.pages_per_chunk)
    # Every item is one content_cache write and one feed_items write; plus a source
    # update per chunk.
    assert meter.usage.writes <= 2 * CAP + len(chunks), meter.usage.describe()
    # Checking content_cache before spending quota costs one read per item, and a source,
    # user and feed read per chunk. Reads are cheap; quota is the scarce resource.
    assert meter.usage.reads <= CAP + 3 * len(chunks) + 5, meter.usage.describe()
    assert await _feed_size(db, alice) == CAP
    assert elapsed < COLD_SYNC_SECONDS, f"cold sync of {CAP} items took {elapsed:.1f}s"
    print(  # noqa: T201
        f"\ncold {CAP}: {youtube.total_units} units {dict(youtube.units)}, "
        f"{meter.usage.describe()}, {len(chunks)} chunks, {elapsed:.1f}s"
    )


async def test_warm_sync_reuses_the_shared_cache(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    meter: FirestoreMeter,
    make_user: Callable[..., EmulatorUser],
) -> None:
    """SPEC §8.3: the n-th user to sync a playlist pays only for the playlistItems walk."""
    alice, bob = make_user(), make_user()
    await _sync(api, alice, await _add(api, alice))
    bob_source = await _add(api, bob)
    youtube.reset()
    meter.reset()

    await _sync(api, bob, bob_source)

    assert youtube.units["videos.list"] == 0, youtube.units
    assert youtube.total_units <= 1 + _pages(CAP), youtube.units
    # Cached videos aren't rewritten: one feed_items write per item, plus source updates.
    assert meter.usage.writes <= CAP + _pages(CAP), meter.usage.describe()
    assert await _feed_size(db, bob) == CAP
    print(f"\nwarm {CAP}: {youtube.total_units} units, {meter.usage.describe()}")  # noqa: T201


async def test_stale_cache_entries_are_refetched(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    make_user: Callable[..., EmulatorUser],
) -> None:
    """SPEC §4.6: a cache entry is reused for 30 days, then refreshed."""
    youtube.video_ids = youtube.video_ids[:PAGE]
    alice, bob = make_user(), make_user()
    await _sync(api, alice, await _add(api, alice))
    old = datetime.now(UTC) - timedelta(days=settings.content_cache_ttl_days, hours=1)
    stale = youtube.video_ids[:10]
    batch = db.batch()
    for vid in stale:
        batch.update(db.collection("content_cache").document(f"yt:{vid}"), {"updated_at": old})
    await batch.commit()

    bob_source = await _add(api, bob)
    youtube.reset()
    await _sync(api, bob, bob_source)
    assert sorted(youtube.detailed) == sorted(stale)


async def test_resync_is_throttled_then_preflighted(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    make_user: Callable[..., EmulatorUser],
) -> None:
    alice = make_user()
    source_id = await _add(api, alice)
    await _sync(api, alice, source_id)

    youtube.reset()
    chunks = await _sync(api, alice, source_id)
    assert youtube.total_units == 0, "a start inside the 15-minute window costs nothing"
    assert chunks[0]["items_synced"] == 0

    await _age(db, source_id, minutes=16)
    youtube.reset()
    await _sync(api, alice, source_id)
    assert dict(youtube.units) == {"playlists.list": 1}, "unchanged: preflight only"


async def test_a_changed_playlist_is_walked_once_then_preflighted(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    make_user: Callable[..., EmulatorUser],
) -> None:
    """After a change is synced, the next unchanged sync is back to one unit."""
    youtube.video_ids = youtube.video_ids[:1000]
    alice = make_user()
    source_id = await _add(api, alice)
    await _sync(api, alice, source_id)

    youtube.grow(10)
    await _age(db, source_id, minutes=16)
    youtube.reset()
    await _sync(api, alice, source_id)
    # The walk re-lists every page, but only the 10 new videos need details.
    assert youtube.units["videos.list"] == 1, youtube.units
    assert await _feed_size(db, alice) == 1010

    await _age(db, source_id, minutes=16)
    youtube.reset()
    await _sync(api, alice, source_id)
    assert dict(youtube.units) == {"playlists.list": 1}, youtube.units


async def test_a_walk_stops_at_the_item_cap(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    youtube: FakeYouTube,
    make_user: Callable[..., EmulatorUser],
) -> None:
    """SPEC §8.2 step 10: a playlist over MAX_ITEMS_PER_SOURCE is walked to the cap, no further.

    Without it the only limit is the app's 40-chunk guard (10,000 items), and a client
    calling the API directly has none.
    """
    youtube.grow(1000)  # 6,000 items
    alice = make_user()
    source_id = await _add(api, alice)
    youtube.reset()
    chunks = await _sync(api, alice, source_id)

    assert youtube.total_units <= 1 + 2 * _pages(CAP), youtube.units
    assert sum(c["items_synced"] for c in chunks) == CAP
    assert await _feed_size(db, alice) == CAP
    source = (await db.collection("sources").document(source_id).get()).to_dict() or {}
    assert source["status"] == "active"
    assert source["next_page_token"] is None
