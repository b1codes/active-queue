"""Provider side of the API contract (contracts/interactions/, ClickUp 86bcxruxt).

Every interaction is replayed against the real app on the Firestore + Auth emulators.
Each response must (1) carry the documented status, (2) validate against the strict
schema in contracts/openapi.json (no undeclared or missing fields), and (3) equal the
recorded example everywhere except the interaction's `dynamic` paths.

After an intentional API change, re-record the examples with
`UPDATE_CONTRACTS=1 make test-backend` and review the diff: the frontend consumer suite
replays the same examples, so a change here that breaks the app fails there.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from firebase_admin import auth

from app.features.content.models import ContentCacheItem
from app.features.content.repository import ContentRepository
from app.features.users.cache import auth_cache
from tests.contract.interactions import (
    Interaction,
    load_files,
    merge_recorded,
    mismatches,
    schema_errors,
    substitute,
    write_file,
)
from tests.contract.paths import UPDATE

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

FILES = load_files()
INTERACTIONS = [it for f in FILES for it in f.interactions]


class States:
    """Provider states. Each returns bindings: placeholder -> real value."""

    def __init__(
        self,
        api: AsyncClient,
        db: FirestoreAsyncClient,
        alice: EmulatorUser,
        seed_feed: Callable[..., Awaitable[list[dict[str, Any]]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self.api, self.db, self.alice = api, db, alice
        self.seed_feed, self.monkeypatch = seed_feed, monkeypatch

    async def provision(self) -> None:
        resp = await self.api.get("/api/v1/users/me", headers=self.alice.headers)
        assert resp.status_code == 200, resp.text

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self.api.post(path, json=body, headers=self.alice.headers)
        assert resp.status_code < 300, resp.text
        data: dict[str, Any] = resp.json()["data"]
        return data

    async def unsynced_small_playlist(self) -> dict[str, str]:
        source = await self._post("/api/v1/sources", {"url_or_id": "fixture-small-playlist"})
        return {"src_1": source["id"]}

    async def synced_small_playlist(self) -> dict[str, str]:
        items = await self.seed_feed(self.alice)
        return {"src_1": items[0]["source_id"]}

    async def pending_session(self) -> dict[str, str]:
        session = await self._post(
            "/api/v1/sessions",
            {
                "activity_id": "running",
                "match_mode": "time_first",
                "target_duration_seconds": 1800,
            },
        )
        return {"sess_1": session["id"]}

    async def in_progress_session(self) -> dict[str, str]:
        bindings = await self.pending_session()
        await self._post(f"/api/v1/sessions/{bindings['sess_1']}/start")
        return bindings

    async def completed_session(self) -> dict[str, str]:
        bindings = await self.in_progress_session()
        await self._post(f"/api/v1/sessions/{bindings['sess_1']}/complete")
        return bindings

    async def livestream_cached(self) -> dict[str, str]:
        """A 0-second item (live broadcast): shorter than every activity's minimum."""
        await ContentRepository(self.db).upsert_content_cache_batch(
            [
                ContentCacheItem(
                    content_id="fx:fx_live_0001",
                    provider="fixture",
                    external_id="fx_live_0001",
                    title="Live 24/7 Lo-Fi Beats Broadcast",
                    duration_seconds=0,
                    published_at=datetime(2025, 1, 30, 12, 0, tzinfo=UTC),
                )
            ]
        )
        return {}

    async def account_disabled(self) -> dict[str, str]:
        ref = self.db.collection("user_authorization").document(self.alice.uid)
        await ref.update({"disabled": True})
        auth_cache.clear()
        return {}

    async def rate_limit_exhausted(self) -> dict[str, str]:
        for _ in range(1000):
            resp = await self.api.get("/api/v1/sessions/active", headers=self.alice.headers)
            if resp.status_code == 429:
                return {}
        pytest.fail("rate limit never tripped")

    async def setup(self, it: Interaction) -> dict[str, str]:
        handlers: dict[str, Callable[[], Awaitable[dict[str, str]]]] = {
            "alice has an unsynced small playlist": self.unsynced_small_playlist,
            "alice has a synced small playlist": self.synced_small_playlist,
            "alice has a pending session": self.pending_session,
            "alice has an in-progress session": self.in_progress_session,
            "alice has a completed session": self.completed_session,
            "a livestream is in the content cache": self.livestream_cached,
            "alice's account is disabled": self.account_disabled,
            "alice has exhausted her rate limit": self.rate_limit_exhausted,
        }
        bindings = {"uid_alice": self.alice.uid}
        if "alice is not provisioned" not in it.states:
            await self.provision()
        for state in it.states:
            if state == "alice is not provisioned":
                continue
            bindings |= await handlers[state]()
        return bindings

    def headers(self, it: Interaction) -> dict[str, str]:
        if it.auth == "none":
            return {}
        if it.auth == "invalid":
            return {"Authorization": "Bearer not-a-jwt"}
        if it.auth == "expired":
            # The Auth emulator skips exp verification, so force the SDK's expiry path.
            def expired(*_args: Any, **_kwargs: Any) -> None:
                raise auth.ExpiredIdTokenError("Token expired", cause=None)

            self.monkeypatch.setattr("app.core.security.auth.verify_id_token", expired)
        return self.alice.headers


KNOWN_STATES = {
    "alice is not provisioned",
    "alice has an unsynced small playlist",
    "alice has a synced small playlist",
    "alice has a pending session",
    "alice has an in-progress session",
    "alice has a completed session",
    "a livestream is in the content cache",
    "alice's account is disabled",
    "alice has exhausted her rate limit",
}


def test_every_state_has_a_handler() -> None:
    used = {s for it in INTERACTIONS for s in it.states}
    assert used <= KNOWN_STATES, f"unknown provider states: {sorted(used - KNOWN_STATES)}"


@pytest.mark.parametrize("it", INTERACTIONS, ids=lambda it: it.id)
async def test_provider_honours_interaction(
    it: Interaction,
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    seed_feed: Callable[..., Awaitable[list[dict[str, Any]]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = States(api, db, alice, seed_feed, monkeypatch)
    bindings = await states.setup(it)
    to_real = bindings
    to_placeholder = {v: k for k, v in bindings.items()}

    kwargs: dict[str, Any] = {"headers": states.headers(it)}
    if it.has_request_body:
        kwargs["json"] = substitute(it.request_body, to_real)
    resp = await api.request(it.method, substitute(it.path, to_real), **kwargs)

    assert resp.status_code == it.status, f"{it.id}: {resp.status_code} {resp.text}"
    body = substitute(resp.json(), to_placeholder)
    errors = schema_errors(it.method, it.path, it.status, body)
    assert not errors, f"{it.id} violates contracts/openapi.json:\n" + "\n".join(errors)

    headers = {k: resp.headers[k] for k in it.response_headers if k in resp.headers}
    if UPDATE:
        _record(it, body, headers)
        return

    diffs = mismatches(it.response_body, body, it.dynamic)
    diffs += mismatches(it.response_headers, headers, it.dynamic, path="headers")
    assert not diffs, f"{it.id} differs from its contract example:\n" + "\n".join(diffs)


def _record(it: Interaction, body: Any, headers: dict[str, str]) -> None:
    it.raw["response"]["body"] = merge_recorded(it.response_body, body, it.dynamic)
    if it.response_headers:
        it.raw["response"]["headers"] = merge_recorded(
            it.response_headers, headers, it.dynamic, path="headers"
        )
    for f in FILES:
        if it in f.interactions:
            write_file(f)
