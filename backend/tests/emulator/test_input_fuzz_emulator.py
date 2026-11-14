"""API-level input fuzzing on the emulators: hostile IDs, source URLs and preferences.

The property every route must keep: malformed input gets a 4xx envelope, never a 500, and
never a write outside the caller's own documents. Real Firestore matters here. Document
ID rules, path interpolation and the provider lookup are what fail on bad IDs, and a
MagicMock client would accept anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.config import settings as app_settings
from app.core.sanitizer import sanitize_text
from tests.unit.test_sanitizer_properties import hostile_text

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from httpx import AsyncClient

    from tests.emulator.conftest import EmulatorUser

API_FUZZ = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

ID_ROUTES = [
    ("DELETE", "/api/v1/sources/{id}"),
    ("POST", "/api/v1/sources/{id}/sync"),
    ("POST", "/api/v1/content/feed/{id}/hide"),
    ("POST", "/api/v1/sessions/{id}/start"),
    ("POST", "/api/v1/sessions/{id}/complete"),
    ("POST", "/api/v1/sessions/{id}/abandon"),
    ("DELETE", "/api/v1/sessions/{id}"),
]


@pytest.fixture(autouse=True)
def _no_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fuzzing sends hundreds of requests from one user; that is not what's under test."""
    for name in ("rate_limit_general", "rate_limit_sync", "rate_limit_heavy", "rate_limit_ip"):
        monkeypatch.setattr(app_settings, name, 1_000_000)


def _assert_envelope(resp: Any) -> None:
    assert resp.status_code < 500, f"{resp.request.method} {resp.request.url} -> {resp.text}"
    if resp.status_code >= 400 and resp.headers.get("content-type", "").startswith(
        "application/json"
    ):
        assert resp.json()["status"] == "error"


@pytest.mark.parametrize(("method", "template"), ID_ROUTES)
@API_FUZZ
@given(raw_id=hostile_text.filter(bool))
async def test_hostile_path_ids_never_500(
    api: AsyncClient, alice: EmulatorUser, method: str, template: str, raw_id: str
) -> None:
    path = template.format(id=quote(raw_id, safe=""))
    resp = await api.request(method, path, headers=alice.headers)
    _assert_envelope(resp)


@API_FUZZ
@given(url_or_id=hostile_text)
async def test_hostile_source_urls_never_500(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, url_or_id: str
) -> None:
    resp = await api.post("/api/v1/sources", json={"url_or_id": url_or_id}, headers=alice.headers)
    _assert_envelope(resp)
    if resp.status_code == 201:
        source = resp.json()["data"]
        assert source["user_id"] == alice.uid
        await api.delete(f"/api/v1/sources/{source['id']}", headers=alice.headers)


_pref_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-(2**70), 2**70),
    st.floats(allow_nan=False, allow_infinity=False),  # JSON has no NaN or inf
    hostile_text,
    st.lists(hostile_text, max_size=30),
    st.dictionaries(st.text(max_size=5), st.integers(), max_size=3),
)


@API_FUZZ
@given(
    body=st.dictionaries(
        st.sampled_from(
            [
                "preferred_activity_types",
                "preferred_tracker_app",
                "default_time_block_seconds",
                "hide_completed",
                "dark_mode",
                "notifications_enabled",
                "uid",
                "email",
                "role",
            ]
        ),
        _pref_values,
        max_size=6,
    )
)
async def test_hostile_preferences_never_500_and_store_only_bounded_values(
    api: AsyncClient, db: FirestoreAsyncClient, alice: EmulatorUser, body: dict[str, Any]
) -> None:
    resp = await api.patch("/api/v1/users/me/preferences", json=body, headers=alice.headers)
    _assert_envelope(resp)

    stored = (await db.collection("users").document(alice.uid).get()).to_dict() or {}
    prefs = stored.get("preferences", {})
    # Mass assignment: identity and role fields in the body are never written.
    assert stored.get("uid", alice.uid) == alice.uid
    assert stored.get("email", alice.email) == alice.email
    auth_doc = (await db.collection("user_authorization").document(alice.uid).get()).to_dict()
    assert (auth_doc or {}).get("role", "user") == "user"

    activities = prefs.get("preferred_activity_types") or []
    assert len(activities) <= 20
    assert all(a == sanitize_text(a, 50) and a for a in activities)
    tracker = prefs.get("preferred_tracker_app")
    assert tracker is None or tracker == sanitize_text(tracker, 50)
    block = prefs.get("default_time_block_seconds")
    assert block is None or 300 <= block <= 86400
