"""Third-party contracts checked against recorded data on every PR (no network).

contracts/third_party/ describes what the backend relies on from the YouTube Data API v3
and Firebase Auth. The same schemas are checked against the real services nightly
(tests/contract/thirdparty/, .github/workflows/contracts-nightly.yml), so a recorded
fixture that drifts from reality is caught there, and a provider change that drifts
from the fixtures is caught here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jsonschema import Draft202012Validator, FormatChecker

from app.core.security import get_current_user
from tests.contract.paths import THIRD_PARTY_DIR

YOUTUBE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "youtube"

# Recorded YouTube response -> the schema of the endpoint it stands in for.
FIXTURE_SCHEMAS = {
    "playlists_ok": "playlists.list",
    "playlists_empty": "playlists.list",
    "playlist_items_page1": "playlistItems.list",
    "playlist_items_page2": "playlistItems.list",
    "playlist_items_page3": "playlistItems.list",
    "videos_page1": "videos.list",
    "videos_page2": "videos.list",
    "videos_page3": "videos.list",
    "error_forbidden": "error",
    "error_playlist_not_found": "error",
    "error_quota": "error",
}


def third_party_validator(name: str) -> Draft202012Validator:
    schema = json.loads((THIRD_PARTY_DIR / f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def errors_for(name: str, instance: Any) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in third_party_validator(name).iter_errors(instance)
    ]


def test_every_recorded_youtube_fixture_is_mapped() -> None:
    on_disk = {p.stem for p in YOUTUBE_FIXTURES.glob("*.json")}
    assert on_disk == FIXTURE_SCHEMAS.keys()


@pytest.mark.parametrize(("fixture", "schema"), FIXTURE_SCHEMAS.items())
def test_recorded_youtube_fixture_satisfies_contract(fixture: str, schema: str) -> None:
    body = json.loads((YOUTUBE_FIXTURES / f"{fixture}.json").read_text())
    errors = errors_for(f"youtube/{schema}", body)
    assert not errors, f"{fixture}.json violates youtube/{schema}:\n" + "\n".join(errors)


FIREBASE_EXAMPLES: dict[str, dict[str, Any]] = {
    p.stem: json.loads(p.read_text())
    for p in sorted((THIRD_PARTY_DIR / "firebase" / "examples").glob("*.json"))
}


@pytest.mark.parametrize("name", FIREBASE_EXAMPLES)
def test_firebase_claim_examples_satisfy_contract(name: str) -> None:
    errors = errors_for("firebase/id_token_claims", FIREBASE_EXAMPLES[name])
    assert not errors, f"{name}:\n" + "\n".join(errors)


@pytest.mark.parametrize("name", FIREBASE_EXAMPLES)
async def test_get_current_user_maps_every_claim_shape(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sign in with Apple may omit name and relay email; the mapping must not depend on them."""
    claims = FIREBASE_EXAMPLES[name]
    # firebase_admin adds `uid` (= sub) to the payload it returns.
    decoded = {**claims, "uid": claims["sub"]}
    monkeypatch.setattr("app.core.security.init_firebase_admin", lambda *_: None)
    monkeypatch.setattr("app.core.security.auth.verify_id_token", lambda *_a, **_k: decoded)

    request = MagicMock()
    user = await get_current_user(
        request, HTTPAuthorizationCredentials(scheme="Bearer", credentials="t")
    )

    assert user.uid == claims["sub"]
    assert user.email == claims.get("email")
    assert user.name == claims.get("name")
    assert user.picture == claims.get("picture")
    assert user.email_verified is claims.get("email_verified", False)
    assert request.state.uid == claims["sub"]


def test_firebase_admin_still_verifies_against_the_contracted_cert_uri() -> None:
    """The nightly cert check is only meaningful if the SDK fetches the same URL."""
    from firebase_admin import _token_gen

    from tests.contract.thirdparty.test_firebase_live import _cert_uri

    assert _cert_uri() == _token_gen.ID_TOKEN_CERT_URI
