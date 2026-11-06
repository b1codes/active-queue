"""Sources, sync engine, feed, hide and matching against real Firestore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.features.content.models import ContentCacheItem

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

    SeedFeed = Callable[..., Awaitable[list[dict[str, Any]]]]
    Provision = Callable[[EmulatorUser], Awaitable[dict[str, Any]]]


async def _add(api: AsyncClient, user: EmulatorUser, url: str) -> Any:
    return await api.post("/api/v1/sources", json={"url_or_id": url}, headers=user.headers)


async def _sync(api: AsyncClient, user: EmulatorUser, source_id: str) -> dict[str, Any]:
    resp = await api.post(f"/api/v1/sources/{source_id}/sync", headers=user.headers)
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()["data"]
    return data


# --------------------------------------------------------------------------- sources


async def test_add_list_delete_source(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    resp = await _add(api, alice, "https://www.youtube.com/playlist?list=fixture-small-playlist")
    assert resp.status_code == 201, resp.text
    src = resp.json()["data"]
    assert src["user_id"] == alice.uid
    assert src["item_count"] == 15
    assert src["status"] == "active"

    listed = (await api.get("/api/v1/sources", headers=alice.headers)).json()["data"]["items"]
    assert [s["id"] for s in listed] == [src["id"]]

    resp = await api.delete(f"/api/v1/sources/{src['id']}", headers=alice.headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == {"source_id": src["id"], "deleted": True}
    assert not (await db.collection("sources").document(src["id"]).get()).exists
    resp = await api.delete(f"/api/v1/sources/{src['id']}", headers=alice.headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    ("url", "status", "code"),
    [
        ("WL", 422, "SOURCE_UNSUPPORTED"),
        ("https://www.youtube.com/playlist?list=LL", 422, "SOURCE_UNSUPPORTED"),
        ("not a url at all", 422, "SOURCE_URL_UNPARSEABLE"),
        ("fixture-unavailable", 404, "SOURCE_NOT_ACCESSIBLE"),
        ("fixture-quota-exceeded", 503, "PROVIDER_QUOTA_EXCEEDED"),
        ("<script>alert(1)</script>", 400, "VALIDATION_FAILED"),
    ],
)
async def test_add_source_rejections(
    api: AsyncClient, alice: EmulatorUser, url: str, status: int, code: str
) -> None:
    resp = await _add(api, alice, url)
    assert resp.status_code == status, resp.text
    assert resp.json()["error"]["code"] == code


async def test_duplicate_and_limit(api: AsyncClient, alice: EmulatorUser) -> None:
    assert (await _add(api, alice, "fixture-small-playlist")).status_code == 201
    dup = await _add(api, alice, "fixture-small-playlist")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "SOURCE_ALREADY_ADDED"
    for i in range(4):
        assert (await _add(api, alice, f"fixture:pl-{i}")).status_code == 201
    over = await _add(api, alice, "fixture:pl-overflow")
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "SOURCE_LIMIT_REACHED"


async def test_sources_are_isolated_per_user(
    api: AsyncClient, alice: EmulatorUser, bob: EmulatorUser
) -> None:
    src = (await _add(api, alice, "fixture-small-playlist")).json()["data"]
    # Same playlist for Bob is not a duplicate.
    assert (await _add(api, bob, "fixture-small-playlist")).status_code == 201
    bob_list = (await api.get("/api/v1/sources", headers=bob.headers)).json()["data"]["items"]
    assert all(s["user_id"] == bob.uid for s in bob_list)
    for method, path in (
        ("delete", f"/api/v1/sources/{src['id']}"),
        ("post", f"/api/v1/sources/{src['id']}/sync"),
    ):
        resp = await getattr(api, method)(path, headers=bob.headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SOURCE_NOT_FOUND"


# --------------------------------------------------------------------------- sync


async def test_chunked_resumable_sync_of_large_playlist(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    src = (await _add(api, alice, "fixture-large-playlist")).json()["data"]
    chunks: list[dict[str, Any]] = []
    for _ in range(40):
        chunk = await _sync(api, alice, src["id"])
        chunks.append(chunk)
        if not chunk["has_more"]:
            break
    # Chunk 1 loses private #10 / deleted #20 (absent upstream) and live #30 (unplayable).
    assert [c["items_synced"] for c in chunks] == [247, 250, 250, 250, 200]
    assert [c["status"] for c in chunks] == ["syncing"] * 4 + ["active"]
    assert chunks[-1]["next_page_token"] is None

    doc = (await db.collection("sources").document(src["id"]).get()).to_dict() or {}
    assert doc["status"] == "active"
    assert doc["next_page_token"] is None
    assert doc["last_sync_at"] is not None

    feed = (await api.get("/api/v1/content/feed?limit=1", headers=alice.headers)).json()
    assert feed["data"]["total_unconsumed"] == 1197


async def test_sync_throttle_preflight_and_full_walk(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    src = (await _add(api, alice, "fixture-small-playlist")).json()["data"]
    first = await _sync(api, alice, src["id"])
    assert first["items_synced"] == 14

    throttled = await _sync(api, alice, src["id"])
    assert throttled["items_synced"] == 0
    assert "throttled" in (throttled["message"] or "").lower()

    ref = db.collection("sources").document(src["id"])
    await ref.update({"last_sync_at": datetime.now(UTC) - timedelta(hours=1)})
    preflight = await _sync(api, alice, src["id"])
    assert preflight["items_synced"] == 0
    assert "no changes" in (preflight["message"] or "").lower()

    await ref.update({"last_sync_at": datetime.now(UTC) - timedelta(days=8)})
    walk = await _sync(api, alice, src["id"])
    assert walk["items_synced"] == 14


async def test_stalled_sync_restarts_from_the_beginning(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    src = (await _add(api, alice, "fixture-large-playlist")).json()["data"]
    await _sync(api, alice, src["id"])
    ref = db.collection("sources").document(src["id"])
    await ref.update({"updated_at": datetime.now(UTC) - timedelta(hours=2)})
    restarted = await _sync(api, alice, src["id"])
    # Stall expiry clears the cursor, so the chunk starts again at offset 0.
    assert restarted["next_page_token"] == "250"


async def test_quota_exhaustion_mid_sync_keeps_cursor(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    src = (await _add(api, alice, "fixture-large-playlist")).json()["data"]
    await _sync(api, alice, src["id"])
    ref = db.collection("sources").document(src["id"])
    await ref.update({"external_source_id": "fixture-quota-exceeded"})
    resp = await api.post(f"/api/v1/sources/{src['id']}/sync", headers=alice.headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PROVIDER_QUOTA_EXCEEDED"
    doc = (await ref.get()).to_dict() or {}
    assert doc["status"] == "quota_paused"
    assert doc["next_page_token"] == "250"
    # Feed stays fully readable while paused (SPEC §8.3).
    feed = await api.get("/api/v1/content/feed", headers=alice.headers)
    assert feed.status_code == 200
    assert feed.json()["data"]["total_unconsumed"] == 247


async def test_resync_does_not_resurface_consumed_items(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    seed_feed: SeedFeed,
) -> None:
    items = await seed_feed(alice)
    hidden = items[0]["content_id"]
    resp = await api.post(f"/api/v1/content/feed/{hidden}/hide", headers=alice.headers)
    assert resp.status_code == 200, resp.text

    src_id = items[0]["source_id"]
    await (
        db.collection("sources")
        .document(src_id)
        .update({"last_sync_at": datetime.now(UTC) - timedelta(days=8)})
    )
    await _sync(api, alice, src_id)

    feed = (await api.get("/api/v1/content/feed?limit=100", headers=alice.headers)).json()
    assert hidden not in {i["content_id"] for i in feed["data"]["items"]}
    assert feed["data"]["total_unconsumed"] == len(items) - 1


async def test_readding_a_removed_source_does_not_resurface_consumed_items(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    items = await seed_feed(alice)
    hidden = items[0]["content_id"]
    await api.post(f"/api/v1/content/feed/{hidden}/hide", headers=alice.headers)
    await api.delete(f"/api/v1/sources/{items[0]['source_id']}", headers=alice.headers)

    again = await seed_feed(alice)
    assert hidden not in {i["content_id"] for i in again}


# --------------------------------------------------------------------------- feed


async def test_feed_pagination_visits_every_item_once(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    all_items = await seed_feed(alice)
    seen: list[str] = []
    cursor: str | None = None
    totals: list[int | None] = []
    for _ in range(10):
        url = "/api/v1/content/feed?limit=4" + (f"&cursor={cursor}" if cursor else "")
        page = (await api.get(url, headers=alice.headers)).json()["data"]
        seen += [i["content_id"] for i in page["items"]]
        totals.append(page["total_unconsumed"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == sorted(i["content_id"] for i in all_items)
    assert len(seen) == len(set(seen))
    # total_unconsumed only on the first page (SPEC §9.2).
    assert totals[0] == 14
    assert all(t is None for t in totals[1:])
    published = [i["published_at"] for i in all_items]
    assert published == sorted(published, reverse=True)


async def test_feed_duration_filter_paginates_through_sparse_matches(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    """Large playlist; only 1-in-5 items are 2700s. Paging must reach all of them."""
    await seed_feed(alice, "fixture-large-playlist")
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(200):
        url = "/api/v1/content/feed?limit=20&min_duration=2700&max_duration=2700" + (
            f"&cursor={cursor}" if cursor else ""
        )
        page = (await api.get(url, headers=alice.headers)).json()["data"]
        assert all(i["duration_seconds"] == 2700 for i in page["items"])
        seen += [i["content_id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen))
    assert len(seen) == 240


async def test_feed_items_are_enriched_from_content_cache(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    items = await seed_feed(alice)
    assert all(i["duration_seconds"] > 0 for i in items)  # unplayable items never queued
    first = next(i for i in items if i["content_id"] == "fx:fx_vid_0001")
    assert first["title"].startswith("Fixture Workout Video #1")
    assert first["provider"] == "fixture"
    assert first["external_id"] == "fx_vid_0001"
    assert first["duration_label"] == "5m 0s"
    assert first["video_url"] == "https://www.youtube.com/watch?v=fx_vid_0001"


async def test_hide_is_scoped_to_the_callers_feed(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    bob: EmulatorUser,
    seed_feed: SeedFeed,
) -> None:
    items = await seed_feed(alice)
    cid = items[0]["content_id"]
    resp = await api.post(f"/api/v1/content/feed/{cid}/hide", headers=bob.headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONTENT_NOT_FOUND"
    doc = (await db.collection("feed_items").document(f"{alice.uid}_{cid}").get()).to_dict()
    assert doc is not None
    assert doc["consumed"] is False

    resp = await api.post(f"/api/v1/content/feed/{cid}/hide", headers=alice.headers)
    assert resp.json()["data"] == {"content_id": cid, "hidden": True}
    user_doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert cid in user_doc["consumed_content_ids"]


# --------------------------------------------------------------------------- matching


async def test_content_match_and_rejections(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    await seed_feed(alice)
    ok = await api.post(
        "/api/v1/content/match", json={"content_id": "fx:fx_vid_0003"}, headers=alice.headers
    )
    assert ok.status_code == 200
    data = ok.json()["data"]
    assert data["duration_seconds"] == 1500
    assert data["is_valid"] is True
    assert {a["id"] for a in data["matching_activities"]} >= {"running", "yoga"}

    short = ContentCacheItem(
        content_id="fx:too_short",
        provider="fixture",
        external_id="too_short",
        title="Two minute warmup",
        duration_seconds=120,
        published_at=datetime.now(UTC),
    )
    await db.collection("content_cache").document(short.content_id).set(short.to_firestore())
    rejected = await api.post(
        "/api/v1/content/match", json={"content_id": "fx:too_short"}, headers=alice.headers
    )
    assert rejected.json()["data"]["is_valid"] is False
    assert rejected.json()["data"]["rejection_reason"] == "duration_out_of_range"

    missing = await api.post(
        "/api/v1/content/match", json={"content_id": "fx:missing"}, headers=alice.headers
    )
    assert missing.status_code == 404


async def test_time_match_windows(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    await seed_feed(alice)

    async def match(target: int) -> dict[str, Any]:
        resp = await api.post(
            "/api/v1/content/match-time",
            json={"target_duration_seconds": target},
            headers=alice.headers,
        )
        assert resp.status_code == 200, resp.text
        data: dict[str, Any] = resp.json()["data"]
        return data

    primary = await match(1500)  # [1500, 1800] contains 1500s items
    assert primary["window_type"] == "primary"
    assert {i["duration_seconds"] for i in primary["matched_items"]} == {1500}

    fallback = await match(1600)  # primary [1600,1900] empty; fallback [1480,1600) has 1500
    assert fallback["window_type"] == "fallback"

    none = await match(3600)
    assert none["is_valid"] is False
    assert none["rejection_reason"] == "no_content_in_window"


@pytest.mark.parametrize(
    "content_id", ["fx:a/b", "a/b/c", "__reserved__", "..", "fx:" + "x" * 1600]
)
async def test_hostile_content_ids_never_500(
    api: AsyncClient, alice: EmulatorUser, content_id: str
) -> None:
    for path, body in (
        ("/api/v1/content/match", {"content_id": content_id}),
        (
            "/api/v1/sessions",
            {"activity_id": "running", "match_mode": "content_first", "content_id": content_id},
        ),
    ):
        resp = await api.post(path, json=body, headers=alice.headers)
        assert resp.status_code in (400, 404, 422), (path, resp.status_code, resp.text)


@pytest.mark.parametrize("bad_id", ["__reserved__", "__x__"])
@pytest.mark.parametrize(
    ("method", "template"),
    [
        ("post", "/api/v1/sessions/{}/start"),
        ("post", "/api/v1/sessions/{}/complete"),
        ("post", "/api/v1/sessions/{}/abandon"),
        ("delete", "/api/v1/sessions/{}"),
        ("delete", "/api/v1/sources/{}"),
        ("post", "/api/v1/sources/{}/sync"),
        ("post", "/api/v1/content/feed/{}/hide"),
    ],
)
async def test_hostile_path_ids_are_400(
    api: AsyncClient, alice: EmulatorUser, bad_id: str, method: str, template: str
) -> None:
    resp = await getattr(api, method)(template.format(bad_id), headers=alice.headers)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_filter_with_no_matches_has_bounded_reads_per_page(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    """A filter that matches nothing must not scan the whole feed in one request."""
    await seed_feed(alice, "fixture-large-playlist")  # 1197 items
    pages = 0
    cursor: str | None = None
    while True:
        pages += 1
        url = "/api/v1/content/feed?limit=20&min_duration=86000" + (
            f"&cursor={cursor}" if cursor else ""
        )
        page = (await api.get(url, headers=alice.headers)).json()["data"]
        assert page["items"] == []
        cursor = page["next_cursor"]
        if not cursor:
            break
        assert pages < 10
    # MAX_FEED_SCAN_PER_REQUEST = 500, so 1197 docs take 3 requests.
    assert pages == 3


async def test_garbage_and_legacy_cursors(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    import base64

    items = await seed_feed(alice)
    garbage = await api.get("/api/v1/content/feed?cursor=%%%not-base64", headers=alice.headers)
    assert garbage.status_code == 200
    # An undecodable cursor falls back to the first page (no 500).
    assert garbage.json()["data"]["items"][0]["content_id"] == items[0]["content_id"]

    legacy = base64.urlsafe_b64encode(items[2]["published_at"].encode()).decode()
    page = (await api.get(f"/api/v1/content/feed?cursor={legacy}", headers=alice.headers)).json()[
        "data"
    ]
    assert page["items"][0]["content_id"] == items[3]["content_id"]

    sessions = await api.get("/api/v1/sessions?cursor=bm90LWEtZGF0ZQ==", headers=alice.headers)
    assert sessions.status_code == 200
