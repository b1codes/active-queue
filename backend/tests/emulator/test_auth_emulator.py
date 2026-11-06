"""Authentication and authorization resolution against the real Auth emulator (SPEC §3)."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import TYPE_CHECKING, Any

import pytest

from app.features.users.cache import auth_cache

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

AUTHENTICATED_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("get", "/api/v1/users/me", None),
    ("patch", "/api/v1/users/me/preferences", {"dark_mode": False}),
    ("get", "/api/v1/sources", None),
    ("post", "/api/v1/sources", {"url_or_id": "fixture-small-playlist"}),
    ("delete", "/api/v1/sources/src_1", None),
    ("post", "/api/v1/sources/src_1/sync", None),
    ("get", "/api/v1/content/feed", None),
    ("post", "/api/v1/content/feed/fx:1/hide", None),
    ("post", "/api/v1/content/match", {"content_id": "fx:1"}),
    ("post", "/api/v1/content/match-time", {"target_duration_seconds": 1800}),
    ("get", "/api/v1/activities", None),
    ("get", "/api/v1/activities/time-blocks", None),
    ("get", "/api/v1/sessions", None),
    ("get", "/api/v1/sessions/active", None),
    ("post", "/api/v1/sessions", {"activity_id": "running", "match_mode": "time_first"}),
    ("post", "/api/v1/sessions/s_1/start", None),
    ("post", "/api/v1/sessions/s_1/complete", None),
    ("post", "/api/v1/sessions/s_1/abandon", None),
    ("delete", "/api/v1/sessions/s_1", None),
]


async def _call(
    api: AsyncClient, method: str, path: str, body: dict[str, Any] | None, headers: dict[str, str]
) -> Any:
    if body is None:
        return await api.request(method.upper(), path, headers=headers)
    return await api.request(method.upper(), path, json=body, headers=headers)


def _unsigned_token(**claims: Any) -> str:
    """Forge an alg=none token; the Admin SDK accepts these only in emulator mode."""

    def b64(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    now = int(time.time())
    payload = {
        "iss": "https://securetoken.google.com/demo-activequeue-local",
        "aud": "demo-activequeue-local",
        "auth_time": now,
        "iat": now,
        "exp": now + 3600,
        "sub": "forged-uid",
        "user_id": "forged-uid",
        **claims,
    }
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}."


@pytest.mark.parametrize(("method", "path", "body"), AUTHENTICATED_ROUTES)
async def test_every_route_requires_a_token(
    api: AsyncClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    resp = await _call(api, method, path, body, {})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_MISSING"


@pytest.mark.parametrize(("method", "path", "body"), AUTHENTICATED_ROUTES)
async def test_disabled_account_is_403_on_every_route(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    await api.get("/api/v1/users/me", headers=alice.headers)
    await db.collection("user_authorization").document(alice.uid).update({"disabled": True})
    auth_cache.clear()  # the 60s TTL bounds staleness; skip the wait
    resp = await _call(api, method, path, body, alice.headers)
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "ACCOUNT_DISABLED"


async def test_status_disabled_is_also_403(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    await (
        db.collection("user_authorization")
        .document(alice.uid)
        .set({"uid": alice.uid, "status": "disabled", "disabled": False})
    )
    resp = await api.get("/api/v1/sessions", headers=alice.headers)
    assert resp.status_code == 403


# Expired tokens are not checked here: in emulator mode the Admin SDK skips signature
# AND exp verification, so AUTH_TOKEN_EXPIRED is covered in tests/unit/test_security.py.
@pytest.mark.parametrize(
    ("token", "code"),
    [
        ("not-a-jwt", "AUTH_TOKEN_INVALID"),
        (_unsigned_token(aud="someone-elses-project"), "AUTH_TOKEN_INVALID"),
        (_unsigned_token(iss="https://evil.example.com/x"), "AUTH_TOKEN_INVALID"),
        (_unsigned_token(sub="", user_id=""), "AUTH_TOKEN_INVALID"),
    ],
)
async def test_bad_tokens_are_401(
    api: AsyncClient, db: FirestoreAsyncClient, token: str, code: str
) -> None:
    resp = await api.get("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == code


async def test_first_request_to_any_route_provisions_the_user(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    resp = await api.get("/api/v1/activities", headers=alice.headers)
    assert resp.status_code == 200
    assert (await db.collection("users").document(alice.uid).get()).exists
    auth_doc = (await db.collection("user_authorization").document(alice.uid).get()).to_dict()
    assert auth_doc is not None
    assert auth_doc["status"] == "active"


async def test_provisioning_never_overwrites_an_existing_profile(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    """users/{uid} exists (e.g. written by a completion) but user_authorization doesn't."""
    await (
        db.collection("users")
        .document(alice.uid)
        .set(
            {
                "uid": alice.uid,
                "email": alice.email,
                "display_name": "Kept",
                "consumed_content_ids": ["fx:keep-me"],
            }
        )
    )
    resp = await api.get("/api/v1/users/me", headers=alice.headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["user"]["display_name"] == "Kept"
    doc = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert doc["consumed_content_ids"] == ["fx:keep-me"]
    assert (await db.collection("user_authorization").document(alice.uid).get()).exists


async def test_concurrent_first_logins_provision_once(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    """The app fires several requests at once on first launch; none may 500."""
    results = await asyncio.gather(
        *(api.get("/api/v1/users/me", headers=alice.headers) for _ in range(8))
    )
    assert {r.status_code for r in results} == {200}
    created = {r.json()["data"]["user"]["created_at"] for r in results}
    assert len(created) == 1


async def test_preferences_patch_is_partial_and_persists(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    resp = await api.patch(
        "/api/v1/users/me/preferences",
        json={"default_time_block_seconds": 1800, "preferred_activity_types": ["yoga", " "]},
        headers=alice.headers,
    )
    assert resp.status_code == 200, resp.text
    prefs = resp.json()["data"]["preferences"]
    assert prefs["default_time_block_seconds"] == 1800
    assert prefs["preferred_activity_types"] == ["yoga"]
    assert prefs["dark_mode"] is True  # untouched default

    resp = await api.patch(
        "/api/v1/users/me/preferences", json={"dark_mode": False}, headers=alice.headers
    )
    prefs = resp.json()["data"]["preferences"]
    assert prefs["dark_mode"] is False
    assert prefs["default_time_block_seconds"] == 1800
    stored = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    assert stored["preferences"]["dark_mode"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"default_time_block_seconds": 10},
        {"default_time_block_seconds": "soon"},
        {"preferred_tracker_app": "x" * 51},
        {"dark_mode": "maybe"},
    ],
)
async def test_preferences_validation(
    api: AsyncClient, alice: EmulatorUser, body: dict[str, Any]
) -> None:
    resp = await api.patch("/api/v1/users/me/preferences", json=body, headers=alice.headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"
