"""Session state machine against real Firestore (SPEC §7, §9.5, §9.6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.features.sessions.models import Session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

    SeedFeed = Callable[..., Awaitable[list[dict[str, Any]]]]
    Provision = Callable[[EmulatorUser], Awaitable[dict[str, Any]]]


def _pick(items: list[dict[str, Any]], duration: int) -> dict[str, Any]:
    return next(i for i in items if i["duration_seconds"] == duration)


async def _create(api: AsyncClient, user: EmulatorUser, **body: Any) -> tuple[int, dict[str, Any]]:
    payload = {"activity_id": "running", "match_mode": "time_first", **body}
    resp = await api.post("/api/v1/sessions", json=payload, headers=user.headers)
    return resp.status_code, resp.json()


async def test_content_first_lifecycle_applies_all_completion_effects(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    provisioned: Provision,
    seed_feed: SeedFeed,
) -> None:
    await provisioned(alice)
    item = _pick(await seed_feed(alice), 1500)
    content_id = item["content_id"]

    code, body = await _create(
        api, alice, match_mode="content_first", content_id=content_id, target_duration_seconds=900
    )
    assert code == 201, body
    session = body["data"]
    # Duration comes from content_cache, never from the request body.
    assert session["duration_seconds"] == 1500
    assert session["status"] == "pending"
    sid = session["id"]

    started = await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "in_progress"

    done = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"

    # All three writes of the completion transaction landed (SPEC §9.6).
    sess_doc = (await db.collection("sessions").document(sid).get()).to_dict() or {}
    feed_doc = (
        await db.collection("feed_items").document(f"{alice.uid}_{content_id}").get()
    ).to_dict() or {}
    user_doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert sess_doc["status"] == "completed"
    assert feed_doc["consumed"] is True
    assert content_id in user_doc["consumed_content_ids"]

    feed = await api.get("/api/v1/content/feed?limit=100", headers=alice.headers)
    assert content_id not in {i["content_id"] for i in feed.json()["data"]["items"]}


async def test_complete_without_prior_users_me_call_succeeds(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    seed_feed: SeedFeed,
) -> None:
    """A client that never called /users/me has no users/{uid} doc; completion must not 500."""
    item = _pick(await seed_feed(alice), 900)
    _, body = await _create(api, alice, match_mode="content_first", content_id=item["content_id"])
    sid = body["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    done = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert done.status_code == 200, done.text
    user_doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert item["content_id"] in user_doc.get("consumed_content_ids", [])


async def test_complete_content_not_in_users_feed_succeeds(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    bob: EmulatorUser,
    provisioned: Provision,
    seed_feed: SeedFeed,
) -> None:
    """Bob may start a session on cached content that isn't in his own feed."""
    item = _pick(await seed_feed(alice), 900)
    await provisioned(bob)
    _, body = await _create(api, bob, match_mode="content_first", content_id=item["content_id"])
    sid = body["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/start", headers=bob.headers)
    done = await api.post(f"/api/v1/sessions/{sid}/complete", headers=bob.headers)
    assert done.status_code == 200, done.text
    # Alice's feed item is untouched.
    alice_feed = (
        await db.collection("feed_items").document(f"{alice.uid}_{item['content_id']}").get()
    ).to_dict() or {}
    assert alice_feed["consumed"] is False


async def test_time_first_session_lifecycle_has_no_content_side_effects(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, provisioned: Provision
) -> None:
    await provisioned(alice)
    code, body = await _create(api, alice, target_duration_seconds=1800)
    assert code == 201, body
    sid = body["data"]["id"]
    assert body["data"]["content_id"] is None
    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    done = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert done.status_code == 200
    user_doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert user_doc.get("consumed_content_ids", []) == []


@pytest.mark.parametrize("duration", [0, 299, 1000, 10800])
async def test_time_first_rejects_off_allowlist_durations(
    api: AsyncClient, alice: EmulatorUser, duration: int
) -> None:
    code, body = await _create(api, alice, target_duration_seconds=duration)
    if duration < 300:
        assert code == 400
        assert body["error"]["code"] == "VALIDATION_FAILED"
    else:
        assert code == 422
        assert body["error"]["code"] == "DURATION_OUT_OF_RANGE"


async def test_activity_duration_mismatch(
    api: AsyncClient, alice: EmulatorUser, seed_feed: SeedFeed
) -> None:
    item = _pick(await seed_feed(alice), 300)  # strength minimum is 600s
    code, body = await _create(
        api,
        alice,
        activity_id="strength",
        match_mode="content_first",
        content_id=item["content_id"],
    )
    assert code == 422
    assert body["error"]["code"] == "ACTIVITY_DURATION_MISMATCH"


async def test_unknown_activity_and_unknown_content_are_404(
    api: AsyncClient, alice: EmulatorUser
) -> None:
    code, body = await _create(api, alice, activity_id="underwater-chess")
    assert code == 404
    assert body["error"]["code"] == "ACTIVITY_NOT_FOUND"
    code, body = await _create(api, alice, match_mode="content_first", content_id="fx:nope")
    assert code == 404
    assert body["error"]["code"] == "CONTENT_NOT_FOUND"


async def test_single_active_session_guardrail(api: AsyncClient, alice: EmulatorUser) -> None:
    _, first = await _create(api, alice, target_duration_seconds=900)
    code, second = await _create(api, alice, target_duration_seconds=900)
    assert code == 409
    assert second["error"]["code"] == "ACTIVE_SESSION_EXISTS"
    assert second["error"]["details"] == [
        {"field": "active_session_id", "issue": first["data"]["id"]}
    ]

    active = await api.get("/api/v1/sessions/active", headers=alice.headers)
    assert active.json()["data"]["id"] == first["data"]["id"]

    # Once terminal, a new session is allowed.
    sid = first["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/abandon", headers=alice.headers)
    code, _ = await _create(api, alice, target_duration_seconds=900)
    assert code == 201


async def test_start_is_idempotent_and_preserves_started_at(
    api: AsyncClient, alice: EmulatorUser
) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    sid = body["data"]["id"]
    first = await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    second = await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    assert second.status_code == 200
    assert first.json()["data"]["started_at"] == second.json()["data"]["started_at"]


async def test_illegal_transitions(api: AsyncClient, alice: EmulatorUser) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    sid = body["data"]["id"]

    resp = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SESSION_NOT_STARTED"

    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    resp = await api.delete(f"/api/v1/sessions/{sid}", headers=alice.headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SESSION_ALREADY_STARTED"

    first = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    again = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert again.status_code == 200  # idempotent
    assert first.json()["data"]["completed_at"] == again.json()["data"]["completed_at"]

    for path, code in (("abandon", 409), ("start", 409)):
        resp = await api.post(f"/api/v1/sessions/{sid}/{path}", headers=alice.headers)
        assert resp.status_code == code, path
        assert resp.json()["error"]["code"] == "SESSION_ALREADY_TERMINAL"
    resp = await api.delete(f"/api/v1/sessions/{sid}", headers=alice.headers)
    assert resp.json()["error"]["code"] == "SESSION_ALREADY_TERMINAL"


async def test_abandon_is_idempotent_and_blocks_completion(
    api: AsyncClient, alice: EmulatorUser
) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    sid = body["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    first = await api.post(f"/api/v1/sessions/{sid}/abandon", headers=alice.headers)
    again = await api.post(f"/api/v1/sessions/{sid}/abandon", headers=alice.headers)
    assert again.status_code == 200
    assert first.json()["data"]["abandoned_at"] == again.json()["data"]["abandoned_at"]
    resp = await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SESSION_ALREADY_TERMINAL"


async def test_discard_hard_deletes_pending_session(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    sid = body["data"]["id"]
    resp = await api.delete(f"/api/v1/sessions/{sid}", headers=alice.headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == {"session_id": sid, "discarded": True}
    assert not (await db.collection("sessions").document(sid).get()).exists
    resp = await api.delete(f"/api/v1/sessions/{sid}", headers=alice.headers)
    assert resp.status_code == 404


async def _insert_stale_session(
    db: FirestoreAsyncClient, uid: str, status: str = "in_progress"
) -> str:
    created = datetime.now(UTC) - timedelta(days=2)
    s = Session(
        id="s_stale_0001",
        user_id=uid,
        activity_id="running",
        match_mode="time_first",
        content_id=None,
        duration_seconds=1800,
        status=status,  # type: ignore[arg-type]
        created_at=created,
        updated_at=created,
    )
    await db.collection("sessions").document(s.id).set(s.to_firestore())
    return s.id


async def test_lazy_abandonment_on_active_read_writes_back(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    sid = await _insert_stale_session(db, alice.uid)
    resp = await api.get("/api/v1/sessions/active", headers=alice.headers)
    assert resp.status_code == 200
    assert resp.json()["data"] is None
    doc = (await db.collection("sessions").document(sid).get()).to_dict() or {}
    assert doc["status"] == "abandoned"
    assert doc["abandoned_at"] is not None
    # The stale session no longer blocks a new one.
    code, _ = await _create(api, alice, target_duration_seconds=900)
    assert code == 201


async def test_lazy_abandonment_on_start(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    sid = await _insert_stale_session(db, alice.uid, status="pending")
    resp = await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SESSION_ALREADY_TERMINAL"


async def test_history_paginates_newest_first_and_filters_by_status(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, bob: EmulatorUser
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        for uid in (alice.uid, bob.uid):
            s = Session(
                id=f"s_{uid[:6]}_{i}",
                user_id=uid,
                activity_id="running",
                match_mode="time_first",
                content_id=None,
                duration_seconds=900,
                status="completed" if i % 2 == 0 else "abandoned",
                created_at=base + timedelta(hours=i),
                updated_at=base + timedelta(hours=i),
            )
            await db.collection("sessions").document(s.id).set(s.to_firestore())

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        url = "/api/v1/sessions?limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = (await api.get(url, headers=alice.headers)).json()["data"]
        seen += [s["id"] for s in page["items"]]
        assert all(s["user_id"] == alice.uid for s in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == [f"s_{alice.uid[:6]}_{i}" for i in (4, 3, 2, 1, 0)]

    completed = (await api.get("/api/v1/sessions?status=completed", headers=alice.headers)).json()[
        "data"
    ]
    assert [s["status"] for s in completed["items"]] == ["completed"] * 3


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("post", "/start"), ("post", "/complete"), ("post", "/abandon"), ("delete", "")],
)
async def test_cross_user_session_access_is_404(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    bob: EmulatorUser,
    method: str,
    suffix: str,
) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    sid = body["data"]["id"]
    if suffix == "/complete":
        await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    before = (await db.collection("sessions").document(sid).get()).to_dict()

    resp = await getattr(api, method)(f"/api/v1/sessions/{sid}{suffix}", headers=bob.headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert (await db.collection("sessions").document(sid).get()).to_dict() == before


async def test_double_tap_complete_is_safe(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    provisioned: Provision,
    seed_feed: SeedFeed,
) -> None:
    """SPEC §7.1: users double-tap; concurrent completes must all succeed, effects once."""
    import asyncio

    await provisioned(alice)
    item = _pick(await seed_feed(alice), 900)
    _, body = await _create(api, alice, match_mode="content_first", content_id=item["content_id"])
    sid = body["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    results = await asyncio.gather(
        *(api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers) for _ in range(4))
    )
    assert [r.status_code for r in results] == [200] * 4, [r.text for r in results]
    assert len({r.json()["data"]["completed_at"] for r in results}) == 1
    user_doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert user_doc["consumed_content_ids"].count(item["content_id"]) == 1


async def test_concurrent_creates_respect_single_active_session(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, provisioned: Provision
) -> None:
    import asyncio

    await provisioned(alice)
    results = await asyncio.gather(
        *(
            api.post(
                "/api/v1/sessions",
                json={
                    "activity_id": "running",
                    "match_mode": "time_first",
                    "target_duration_seconds": 900,
                },
                headers=alice.headers,
            )
            for _ in range(5)
        )
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409, 409], [r.text for r in results]
    active = [
        s
        for s in await db.collection("sessions").get()
        if (s.to_dict() or {})["status"] in ("pending", "in_progress")
    ]
    assert len(active) == 1


async def test_slot_is_reclaimed_after_discard_and_completion(
    api: AsyncClient, alice: EmulatorUser
) -> None:
    _, body = await _create(api, alice, target_duration_seconds=900)
    await api.delete(f"/api/v1/sessions/{body['data']['id']}", headers=alice.headers)
    code, body = await _create(api, alice, target_duration_seconds=900)
    assert code == 201, body
    sid = body["data"]["id"]
    await api.post(f"/api/v1/sessions/{sid}/start", headers=alice.headers)
    await api.post(f"/api/v1/sessions/{sid}/complete", headers=alice.headers)
    code, body = await _create(api, alice, target_duration_seconds=900)
    assert code == 201, body
