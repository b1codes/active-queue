"""Users & auth against the real Auth + Firestore emulators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser


async def test_first_login_provisions_both_documents_atomically(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser
) -> None:
    resp = await api.get("/api/v1/users/me", headers=alice.headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["user"]["uid"] == alice.uid
    assert body["data"]["user"]["display_name"] == "Alice"
    assert body["data"]["authorization"]["status"] == "active"

    user_snap = await db.collection("users").document(alice.uid).get()
    auth_snap = await db.collection("user_authorization").document(alice.uid).get()
    assert user_snap.exists
    assert auth_snap.exists
    assert (user_snap.to_dict() or {})["email"] == "alice@example.com"


async def test_second_login_does_not_reprovision(
    api: AsyncClient,
    db: FirestoreAsyncClient,
    alice: EmulatorUser,
    provisioned: Callable[[EmulatorUser], Awaitable[dict[str, Any]]],
) -> None:
    first = await provisioned(alice)
    await db.collection("users").document(alice.uid).update({"display_name": "Renamed"})
    second = await provisioned(alice)
    assert second["user"]["display_name"] == "Renamed"
    assert second["user"]["created_at"] == first["user"]["created_at"]
