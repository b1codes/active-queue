"""Emulator-backed integration tier.

These tests run the real FastAPI app against the Firestore and Firebase Auth emulators.
Nothing is mocked below the HTTP layer: ID tokens are minted by the Auth emulator and
verified by firebase_admin, and every repository call issues real Firestore queries,
batches, and transactions.

Hosts come from the standard SDK environment variables, which `firebase emulators:exec`
sets automatically. When they are absent we fall back to the ports in
`firebase.test.json` (9190 / 9199), which differ from the dev emulators in
`firebase.json` so a test run never wipes local dev data.

If the emulators are unreachable the whole tier is skipped, unless REQUIRE_EMULATOR=1
(set in CI), in which case it fails loudly instead of silently skipping.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import firebase_admin
import httpx
import pytest
from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import account_status_cache
from app.features.users.cache import auth_cache
from app.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

PROJECT_ID = settings.gcp_project_id
FIRESTORE_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:9190")
AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9199")


def _emulators_reachable() -> bool:
    try:
        httpx.get(f"http://{FIRESTORE_HOST}/", timeout=1.0)
        httpx.get(f"http://{AUTH_HOST}/", timeout=1.0)
    except httpx.HTTPError:
        return False
    return True


_REACHABLE = _emulators_reachable()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    here = os.path.dirname(__file__)
    ours = [item for item in items if str(item.fspath).startswith(here)]
    if not ours:
        return
    if not _REACHABLE and os.environ.get("REQUIRE_EMULATOR") == "1":
        pytest.exit(
            f"REQUIRE_EMULATOR=1 but emulators are unreachable at {FIRESTORE_HOST} / {AUTH_HOST}",
            returncode=1,
        )
    for item in ours:
        item.add_marker(pytest.mark.emulator)
        if not _REACHABLE:
            item.add_marker(
                pytest.mark.skip(
                    reason=f"emulators unreachable at {FIRESTORE_HOST} / {AUTH_HOST} "
                    "(run `make test-emulator`)"
                )
            )


def _reset_emulators() -> None:
    httpx.delete(
        f"http://{FIRESTORE_HOST}/emulator/v1/projects/{PROJECT_ID}/databases/(default)/documents",
        timeout=10.0,
    ).raise_for_status()
    httpx.delete(
        f"http://{AUTH_HOST}/emulator/v1/projects/{PROJECT_ID}/accounts",
        timeout=10.0,
    ).raise_for_status()


@pytest.fixture
async def db(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[FirestoreAsyncClient]:
    """Real Firestore AsyncClient pointed at a freshly wiped emulator."""
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", FIRESTORE_HOST)
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", AUTH_HOST)
    monkeypatch.setattr(settings, "firestore_emulator_host", FIRESTORE_HOST)
    monkeypatch.setattr(settings, "firebase_auth_emulator_host", AUTH_HOST)
    monkeypatch.setattr(settings, "content_provider", "fixture")

    # firebase_admin caches the emulator host per App; rebuild it against our ports.
    with contextlib.suppress(ValueError):
        firebase_admin.delete_app(firebase_admin.get_app())
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

    _reset_emulators()
    auth_cache.clear()
    account_status_cache.clear()

    client = FirestoreAsyncClient(project=PROJECT_ID)
    monkeypatch.setattr("app.core.firestore._client", client)
    yield client
    client.close()  # type: ignore[no-untyped-call]
    auth_cache.clear()
    account_status_cache.clear()


@dataclass
class EmulatorUser:
    uid: str
    email: str
    id_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.id_token}"}


def _sign_up(email: str, display_name: str | None = None) -> EmulatorUser:
    payload: dict[str, Any] = {
        "email": email,
        "password": "emulator-password",
        "returnSecureToken": True,
    }
    if display_name:
        payload["displayName"] = display_name
    resp = httpx.post(
        f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        json=payload,
        timeout=10.0,
    )
    resp.raise_for_status()
    body = resp.json()
    return EmulatorUser(uid=body["localId"], email=email, id_token=body["idToken"])


@pytest.fixture
def make_user(db: FirestoreAsyncClient) -> Callable[..., EmulatorUser]:
    """Create a real Auth-emulator account and return its ID token."""

    def _make(email: str | None = None, display_name: str | None = None) -> EmulatorUser:
        return _sign_up(email or f"user-{uuid.uuid4().hex[:8]}@example.com", display_name)

    return _make


@pytest.fixture
async def api(db: FirestoreAsyncClient) -> AsyncGenerator[AsyncClient]:
    """ASGI client for the real app; requests hit the emulator-backed Firestore client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def alice(make_user: Callable[..., EmulatorUser]) -> EmulatorUser:
    return make_user("alice@example.com", "Alice")


@pytest.fixture
def bob(make_user: Callable[..., EmulatorUser]) -> EmulatorUser:
    return make_user("bob@example.com", "Bob")


@pytest.fixture
def provisioned(
    api: AsyncClient,
) -> Callable[[EmulatorUser], Awaitable[dict[str, Any]]]:
    """Provision a user via GET /users/me (first-login path) and return the payload."""

    async def _provision(user: EmulatorUser) -> dict[str, Any]:
        resp = await api.get("/api/v1/users/me", headers=user.headers)
        assert resp.status_code == 200, resp.text
        data: dict[str, Any] = resp.json()["data"]
        return data

    return _provision


@pytest.fixture
def seed_feed(
    api: AsyncClient,
) -> Callable[..., Awaitable[list[dict[str, Any]]]]:
    """Add a fixture playlist for `user`, sync it to completion, and return the feed items."""

    async def _seed(
        user: EmulatorUser, playlist: str = "fixture-small-playlist"
    ) -> list[dict[str, Any]]:
        created = await api.post(
            "/api/v1/sources", json={"url_or_id": playlist}, headers=user.headers
        )
        assert created.status_code == 201, created.text
        source_id = created.json()["data"]["id"]
        for _ in range(40):  # SPEC §9.4 client loop guard
            sync = await api.post(f"/api/v1/sources/{source_id}/sync", headers=user.headers)
            assert sync.status_code == 200, sync.text
            if not sync.json()["data"]["has_more"]:
                break
        feed = await api.get("/api/v1/content/feed?limit=100", headers=user.headers)
        assert feed.status_code == 200, feed.text
        items: list[dict[str, Any]] = feed.json()["data"]["items"]
        return items

    return _seed
