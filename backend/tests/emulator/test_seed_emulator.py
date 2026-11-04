"""`make seed-db` against the emulators: the seeded data must be usable through the API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.cli.seed import seed_db
from tests.emulator.conftest import AUTH_HOST

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient
    from pytest import CaptureFixture, MonkeyPatch


def _sign_in(email: str, password: str) -> dict[str, str]:
    resp = httpx.post(
        f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        "?key=fake-api-key",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=10.0,
    )
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['idToken']}"}


async def test_seed_is_idempotent_and_consistent(
    api: AsyncClient, db: FirestoreAsyncClient, capsys: CaptureFixture[str]
) -> None:
    first = await seed_db(clear=True, quiet=False)
    assert "Database seeding completed" in capsys.readouterr().out
    second = await seed_db(clear=True, quiet=True)
    assert first == second
    assert first["users"] >= 1
    assert first["feed_items"] > 0

    # Invariants the API relies on.
    users = {d.id: d.to_dict() or {} for d in await db.collection("users").get()}
    for feed in await db.collection("feed_items").get():
        item = feed.to_dict() or {}
        consumed_ids = users.get(item["user_id"], {}).get("consumed_content_ids", [])
        assert item["consumed"] == (item["content_id"] in consumed_ids), item["id"]
        assert item["duration_seconds"] > 0
        assert (await db.collection("content_cache").document(item["content_id"]).get()).exists

    active_by_user: dict[str, int] = {}
    for sess in await db.collection("sessions").get():
        s = sess.to_dict() or {}
        if s["status"] in ("pending", "in_progress"):
            active_by_user[s["user_id"]] = active_by_user.get(s["user_id"], 0) + 1
    assert all(n <= 1 for n in active_by_user.values()), active_by_user


async def test_seeded_primary_user_can_use_the_app(
    api: AsyncClient, db: FirestoreAsyncClient, monkeypatch: MonkeyPatch
) -> None:
    await seed_db(clear=True, quiet=True)
    # seed_db closes the process-wide client on exit (it is a CLI); restore ours.
    monkeypatch.setattr("app.core.firestore._client", db)
    headers = _sign_in("test@activequeue.dev", "password123")

    me = await api.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["user"]["uid"] == "test-user-123"

    feed = await api.get("/api/v1/content/feed", headers=headers)
    assert feed.status_code == 200
    assert feed.json()["data"]["items"]

    assert (await api.get("/api/v1/sources", headers=headers)).status_code == 200
    assert (await api.get("/api/v1/sessions", headers=headers)).status_code == 200

    # The seeded in-progress session is the active one and blocks a second.
    active = (await api.get("/api/v1/sessions/active", headers=headers)).json()["data"]
    assert active["id"] == "session_seed_in_progress_01"
    blocked = await api.post(
        "/api/v1/sessions",
        json={
            "activity_id": "running",
            "match_mode": "time_first",
            "target_duration_seconds": 900,
        },
        headers=headers,
    )
    assert blocked.status_code == 409

    # The seeded in-progress session is the active one and blocks a second.
    active = (await api.get("/api/v1/sessions/active", headers=headers)).json()["data"]
    assert active["id"] == "session_seed_in_progress_01"
    blocked = await api.post(
        "/api/v1/sessions",
        json={
            "activity_id": "running",
            "match_mode": "time_first",
            "target_duration_seconds": 900,
        },
        headers=headers,
    )
    assert blocked.status_code == 409
