"""Firestore reads and writes per request stay bounded as a user's data grows.

Firestore bills per document, so a request whose reads grow with the user's data gets
slower and dearer for exactly the users who use the app most. Each endpoint runs here as
a heavy user: 4 sources (one a 1,200-item playlist, synced), 30 completed sessions and a
consumed list. Each one is held to a budget derived from what bounds it (a page size, the
5-source cap, the time-match result cap). How reads are counted is in
`tests/firestore_meter.py`.

A request that reads in proportion to the user's data blows its budget here. Before
time-first matching was fixed, `match-time` read 250 feed items and still found nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from app.core.config import settings
from app.core.security import account_status_cache
from app.features.content.matcher import TIME_MATCH_RESULT_LIMIT
from app.features.content.repository import MAX_FEED_SCAN_PER_REQUEST
from app.features.users.cache import auth_cache
from app.middleware.ratelimit import _limiter
from tests.firestore_meter import FirestoreMeter

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

HISTORY_SESSIONS = 30
FEED_PAGE = 20
SESSIONS_PAGE = 20
MAX_SOURCES = 5
# A count() costs one read per 1,000 matches: up to 25 for a user at every cap.
COUNT_READS = MAX_SOURCES * settings.max_items_per_source // 1000


@dataclass(frozen=True)
class Budget:
    reads: int
    writes: int = 0


@pytest.fixture
def meter(db: FirestoreAsyncClient, monkeypatch: pytest.MonkeyPatch) -> FirestoreMeter:
    m = FirestoreMeter()
    m.install(monkeypatch)
    return m


async def _sync_all(api: AsyncClient, user: EmulatorUser, source_id: str) -> None:
    for _ in range(40):
        _limiter.reset()
        resp = await api.post(f"/api/v1/sources/{source_id}/sync", headers=user.headers)
        assert resp.status_code == 200, resp.text
        if not resp.json()["data"]["has_more"]:
            return
    pytest.fail("sync never finished")


async def _clear_active(api: AsyncClient, user: EmulatorUser) -> None:
    active = await api.get("/api/v1/sessions/active", headers=user.headers)
    session = active.json()["data"]
    if session:
        sid = session["id"]
        resp = await (
            api.delete(f"/api/v1/sessions/{sid}", headers=user.headers)
            if session["status"] == "pending"
            else api.post(f"/api/v1/sessions/{sid}/abandon", headers=user.headers)
        )
        assert resp.status_code < 300, resp.text


async def _session(
    api: AsyncClient,
    user: EmulatorUser,
    *,
    start: bool,
    complete: bool,
    content_id: str | None = None,
) -> str:
    _limiter.reset()
    await _clear_active(api, user)
    body: dict[str, Any] = (
        {"match_mode": "content_first", "content_id": content_id}
        if content_id
        else {"match_mode": "time_first", "target_duration_seconds": 900}
    )
    created = await api.post(
        "/api/v1/sessions", json={"activity_id": "running", **body}, headers=user.headers
    )
    assert created.status_code == 201, created.text
    session_id: str = created.json()["data"]["id"]
    if start:
        started = await api.post(f"/api/v1/sessions/{session_id}/start", headers=user.headers)
        assert started.status_code == 200, started.text
    if complete:
        done = await api.post(
            f"/api/v1/sessions/{session_id}/complete", json={}, headers=user.headers
        )
        assert done.status_code == 200, done.text
    return session_id


async def _populate(api: AsyncClient, user: EmulatorUser) -> dict[str, str]:
    """Give `user` the heavy data set; return IDs the requests below need."""
    sources = []
    for playlist in ["fixture:pl-large", "fixture-small-playlist", "fixture:pl-b", "fixture:pl-c"]:
        _limiter.reset()
        resp = await api.post(
            "/api/v1/sources", json={"url_or_id": playlist}, headers=user.headers
        )
        assert resp.status_code == 201, resp.text
        sources.append(resp.json()["data"]["id"])
    await _sync_all(api, user, sources[0])

    for _ in range(HISTORY_SESSIONS):
        await _session(api, user, start=True, complete=True)
    feed = await api.get("/api/v1/content/feed?limit=100", headers=user.headers)
    for item in feed.json()["data"]["items"][-10:]:
        _limiter.reset()
        hidden = await api.post(
            f"/api/v1/content/feed/{item['content_id']}/hide", headers=user.headers
        )
        assert hidden.status_code == 200, hidden.text

    _limiter.reset()
    page = (await api.get(f"/api/v1/content/feed?limit={FEED_PAGE}", headers=user.headers)).json()
    items = page["data"]["items"]
    return {
        "content": items[0]["content_id"],
        "hide": items[1]["content_id"],
        "complete": items[2]["content_id"],
        "cursor": page["data"]["next_cursor"],
    }


Request = tuple[str, str, dict[str, Any] | None]
Builder = Callable[["AsyncClient", "EmulatorUser", dict[str, str]], Awaitable[Request]]

# (name, budget, request builder). A builder may first create the state its request needs
# (a session to start, say); only the request it returns is metered.
CASES: list[tuple[str, Budget, Builder]] = []


def case(name: str, budget: Budget) -> Callable[[Builder], Builder]:
    def register(fn: Builder) -> Builder:
        CASES.append((name, budget, fn))
        return fn

    return register


@case("any request, auth caches cold", Budget(reads=1))
async def _cold_auth(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    # Once per user per auth_cache_ttl_seconds: the account-status and provisioning checks.
    auth_cache.clear()
    account_status_cache.clear()
    return "GET", "/api/v1/activities", None


@case("GET /users/me", Budget(reads=1))
async def _me(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", "/api/v1/users/me", None


@case("PATCH /users/me/preferences", Budget(reads=4, writes=1))
async def _prefs(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "PATCH", "/api/v1/users/me/preferences", {"haptics_enabled": False}


@case("GET /sources", Budget(reads=MAX_SOURCES))
async def _sources(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", "/api/v1/sources", None


@case("POST /sources", Budget(reads=MAX_SOURCES + 1, writes=1))
async def _add_source(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "POST", "/api/v1/sources", {"url_or_id": "fixture:pl-new"}


@case("DELETE /sources/{id}", Budget(reads=1, writes=1))
async def _delete_source(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "DELETE", f"/api/v1/sources/{user.uid}_fixture_pl-new", None


# A page reads limit + 1 feed items (the +1 says whether a next page exists) and the
# limit's content_cache documents. The first page adds the total_unconsumed count().
@case("GET /content/feed", Budget(reads=2 * FEED_PAGE + 1 + COUNT_READS))
async def _feed(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", f"/api/v1/content/feed?limit={FEED_PAGE}", None


@case("GET /content/feed (next page)", Budget(reads=2 * FEED_PAGE + 1))
async def _feed_next(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", f"/api/v1/content/feed?limit={FEED_PAGE}&cursor={ids['cursor']}", None


# Duration filters are applied in memory, so a filter that matches little scans up to
# MAX_FEED_SCAN_PER_REQUEST items and returns a cursor to resume. The app doesn't send
# them; the cap keeps a client that does from reading a whole feed per request.
@case(
    "GET /content/feed (duration filter)",
    Budget(reads=MAX_FEED_SCAN_PER_REQUEST + FEED_PAGE + COUNT_READS),
)
async def _feed_filtered(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", f"/api/v1/content/feed?limit={FEED_PAGE}&min_duration=3500", None


@case("POST /content/feed/{id}/hide", Budget(reads=1, writes=2))
async def _hide(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "POST", f"/api/v1/content/feed/{ids['hide']}/hide", None


@case("POST /content/match", Budget(reads=1))
async def _match(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "POST", "/api/v1/content/match", {"content_id": ids["content"]}


@case("POST /content/match-time (primary)", Budget(reads=2 * TIME_MATCH_RESULT_LIMIT))
async def _match_time(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "POST", "/api/v1/content/match-time", {"target_duration_seconds": 1800}


# An empty primary window still costs its query one read.
@case("POST /content/match-time (fallback)", Budget(reads=2 * TIME_MATCH_RESULT_LIMIT + 1))
async def _match_fallback(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "POST", "/api/v1/content/match-time", {"target_duration_seconds": 2200}


@case("GET /activities", Budget(reads=0))
async def _activities(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", "/api/v1/activities", None


@case("GET /sessions", Budget(reads=SESSIONS_PAGE + 1))
async def _sessions(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", f"/api/v1/sessions?limit={SESSIONS_PAGE}", None


@case("GET /sessions/active", Budget(reads=1))
async def _active(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    return "GET", "/api/v1/sessions/active", None


@case("POST /sessions", Budget(reads=4, writes=4))
async def _create(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    await _clear_active(api, user)
    return (
        "POST",
        "/api/v1/sessions",
        {"activity_id": "running", "match_mode": "content_first", "content_id": ids["content"]},
    )


@case("POST /sessions/{id}/start", Budget(reads=1, writes=1))
async def _start(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    session_id = await _session(api, user, start=False, complete=False)
    return "POST", f"/api/v1/sessions/{session_id}/start", None


# One transaction: the session, its feed item and the user's consumed list.
@case("POST /sessions/{id}/complete", Budget(reads=2, writes=3))
async def _complete(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    session_id = await _session(api, user, start=True, complete=False, content_id=ids["complete"])
    return "POST", f"/api/v1/sessions/{session_id}/complete", {}


@case("POST /sessions/{id}/abandon", Budget(reads=1, writes=2))
async def _abandon(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    session_id = await _session(api, user, start=True, complete=False)
    return "POST", f"/api/v1/sessions/{session_id}/abandon", None


@case("DELETE /sessions/{id}", Budget(reads=1, writes=2))
async def _discard(api: AsyncClient, user: EmulatorUser, ids: dict[str, str]) -> Request:
    session_id = await _session(api, user, start=False, complete=False)
    return "DELETE", f"/api/v1/sessions/{session_id}", None


async def test_every_request_stays_within_its_firestore_budget(
    api: AsyncClient, meter: FirestoreMeter, make_user: Callable[..., EmulatorUser]
) -> None:
    user = make_user()
    ids = await _populate(api, user)

    report: list[str] = []
    failures: list[str] = []
    for name, budget, build in CASES:
        method, url, body = await build(api, user, ids)
        _limiter.reset()
        if name != "any request, auth caches cold":
            # Warm the auth caches, as any request after a user's first finds them.
            await api.get("/api/v1/activities", headers=user.headers)
        meter.reset()
        resp = await api.request(method, url, json=body, headers=user.headers)
        assert resp.status_code < 300, f"{name}: {resp.status_code} {resp.text}"
        usage = meter.usage
        report.append(f"{name}: {usage.describe()}")
        if usage.reads > budget.reads or usage.writes > budget.writes:
            failures.append(
                f"{name}: {usage.describe()}; budget {budget.reads} reads, {budget.writes} writes"
            )
    print("\n" + "\n".join(report))  # noqa: T201  (pytest -s shows the full table)
    assert not failures, "Over budget:\n" + "\n".join(failures)
