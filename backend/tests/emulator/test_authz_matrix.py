"""Authorization matrix: every operation in the API, attacked by a second user.

The inventory is the app's own OpenAPI document, so adding a route without classifying it
here fails test_every_operation_is_classified. Each classification states what the
operation may do when Bob calls it while Alice has a full set of data:

- OWNED: the path carries an ID of an owner-scoped resource. Bob gets the resource's 404,
  never a 403 (which would confirm the ID exists).
- CALLER_SCOPED: lists, reads, or writes the caller's own data. Bob's response must not
  mention any of Alice's identifiers.
- SHARED: global catalogs and the shared content cache. Not user data by design (SPEC §4).

For every operation, Alice's documents must be byte-for-byte unchanged after Bob's call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import pytest

from app.main import app

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient, Response

    from tests.emulator.conftest import EmulatorUser


class Access(Enum):
    OWNED = "owned"
    CALLER_SCOPED = "caller_scoped"
    SHARED = "shared"


@dataclass(frozen=True)
class Op:
    access: Access
    body: Callable[[AliceWorld], dict[str, Any]] | None = None
    not_found_code: str | None = None


@dataclass(frozen=True)
class AliceWorld:
    source_id: str
    content_id: str
    session_id: str

    @property
    def path_params(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "content_id": self.content_id,
            "session_id": self.session_id,
        }


V1 = "/api/v1"

MATRIX: dict[tuple[str, str], Op] = {
    ("GET", f"{V1}/users/me"): Op(Access.CALLER_SCOPED),
    ("PATCH", f"{V1}/users/me/preferences"): Op(
        Access.CALLER_SCOPED, body=lambda _w: {"dark_mode": False}
    ),
    ("GET", f"{V1}/sources"): Op(Access.CALLER_SCOPED),
    ("POST", f"{V1}/sources"): Op(
        Access.CALLER_SCOPED, body=lambda _w: {"url_or_id": "fixture-small-playlist"}
    ),
    ("DELETE", f"{V1}/sources/{{source_id}}"): Op(Access.OWNED, not_found_code="SOURCE_NOT_FOUND"),
    ("POST", f"{V1}/sources/{{source_id}}/sync"): Op(
        Access.OWNED, not_found_code="SOURCE_NOT_FOUND"
    ),
    ("GET", f"{V1}/content/feed"): Op(Access.CALLER_SCOPED),
    ("POST", f"{V1}/content/feed/{{content_id}}/hide"): Op(
        Access.OWNED, not_found_code="CONTENT_NOT_FOUND"
    ),
    # Matching reads the shared content cache, not anyone's feed.
    ("POST", f"{V1}/content/match"): Op(
        Access.SHARED, body=lambda w: {"content_id": w.content_id}
    ),
    ("POST", f"{V1}/content/match-time"): Op(
        Access.CALLER_SCOPED, body=lambda _w: {"target_duration_seconds": 1800}
    ),
    ("GET", f"{V1}/activities"): Op(Access.SHARED),
    ("GET", f"{V1}/activities/time-blocks"): Op(Access.SHARED),
    ("GET", f"{V1}/sessions"): Op(Access.CALLER_SCOPED),
    ("GET", f"{V1}/sessions/active"): Op(Access.CALLER_SCOPED),
    ("POST", f"{V1}/sessions"): Op(
        Access.CALLER_SCOPED,
        body=lambda w: {
            "activity_id": "running",
            "match_mode": "content_first",
            "content_id": w.content_id,
        },
    ),
    ("POST", f"{V1}/sessions/{{session_id}}/start"): Op(
        Access.OWNED, not_found_code="SESSION_NOT_FOUND"
    ),
    ("POST", f"{V1}/sessions/{{session_id}}/complete"): Op(
        Access.OWNED, not_found_code="SESSION_NOT_FOUND"
    ),
    ("POST", f"{V1}/sessions/{{session_id}}/abandon"): Op(
        Access.OWNED, not_found_code="SESSION_NOT_FOUND"
    ),
    ("DELETE", f"{V1}/sessions/{{session_id}}"): Op(
        Access.OWNED, not_found_code="SESSION_NOT_FOUND"
    ),
}

PUBLIC = {("GET", "/health"), ("GET", "/healthz")}


def _inventory() -> set[tuple[str, str]]:
    paths: dict[str, dict[str, Any]] = app.openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def test_every_operation_is_classified() -> None:
    inventory = _inventory()
    assert inventory - PUBLIC - MATRIX.keys() == set(), "classify the new route in MATRIX"
    assert MATRIX.keys() - inventory == set(), "MATRIX lists a route that no longer exists"


def _fill(template: str, params: dict[str, str]) -> str:
    return template.format(**params)


@pytest.mark.parametrize(("method", "template"), sorted(MATRIX))
async def test_every_operation_requires_a_token(
    api: AsyncClient, method: str, template: str
) -> None:
    path = _fill(template, {"source_id": "s", "content_id": "c", "session_id": "x"})
    resp = await api.request(method, path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_MISSING"


_OWNED_COLLECTIONS = ("users", "user_authorization", "sources", "feed_items", "sessions")


async def _snapshot(db: FirestoreAsyncClient, uid: str) -> dict[str, dict[str, Any]]:
    """Every document Alice owns, keyed by path."""
    docs: dict[str, dict[str, Any]] = {}
    for name in _OWNED_COLLECTIONS:
        async for doc in db.collection(name).stream():
            data = doc.to_dict() or {}
            if doc.id == uid or data.get("user_id") == uid or data.get("uid") == uid:
                docs[f"{name}/{doc.id}"] = data
    return docs


@pytest.fixture
async def alice_world(
    api: AsyncClient,
    alice: EmulatorUser,
    seed_feed: Callable[..., Awaitable[list[dict[str, Any]]]],
) -> AliceWorld:
    """Alice has a synced source, a feed, and a started session: every resource kind."""
    items = await seed_feed(alice)
    sources = (await api.get(f"{V1}/sources", headers=alice.headers)).json()["data"]["items"]
    created = await api.post(
        f"{V1}/sessions",
        json={
            "activity_id": "running",
            "match_mode": "content_first",
            "content_id": items[0]["content_id"],
        },
        headers=alice.headers,
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["data"]["id"]
    started = await api.post(f"{V1}/sessions/{session_id}/start", headers=alice.headers)
    assert started.status_code == 200, started.text
    return AliceWorld(
        source_id=sources[0]["id"],
        content_id=items[1]["content_id"],
        session_id=session_id,
    )


def _alice_identifiers(alice: EmulatorUser, world: AliceWorld) -> list[str]:
    return [alice.uid, alice.email, world.source_id, world.session_id]


async def _call(
    api: AsyncClient, method: str, path: str, op: Op, world: AliceWorld, user: EmulatorUser
) -> Response:
    body = op.body(world) if op.body else None
    return await api.request(method, path, json=body, headers=user.headers)


@pytest.mark.parametrize(("method", "template"), sorted(MATRIX))
async def test_second_user_cannot_reach_the_first_users_data(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    bob: EmulatorUser,
    alice_world: AliceWorld,
    method: str,
    template: str,
) -> None:
    op = MATRIX[(method, template)]
    before = await _snapshot(db, alice.uid)
    assert before, "alice_world should have created documents"

    resp = await _call(api, method, _fill(template, alice_world.path_params), op, alice_world, bob)

    if op.access is Access.OWNED:
        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == op.not_found_code
    else:
        assert resp.status_code < 500, resp.text
        for identifier in _alice_identifiers(alice, alice_world):
            assert identifier not in resp.text, f"{identifier!r} leaked to another user"

    assert await _snapshot(db, alice.uid) == before
