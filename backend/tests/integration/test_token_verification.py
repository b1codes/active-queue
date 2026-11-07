"""Firebase ID token verification through the real Admin SDK path (SPEC §3.1).

The emulator tier cannot test this: in emulator mode firebase_admin skips signature,
algorithm and expiry checks entirely. Here the Admin SDK runs in production mode, and the
only thing faked is the Google certificate endpoint, which serves a certificate for a key
generated per test session. Every token below is minted and signed for real.
"""

from __future__ import annotations

import base64
import contextlib
import datetime as dt
import json
import time
from typing import TYPE_CHECKING, Any

import firebase_admin
import google.oauth2.id_token
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from firebase_admin import auth, credentials
from firebase_admin.exceptions import UnavailableError
from google.auth import credentials as google_credentials
from google.auth import crypt
from google.auth import exceptions as google_auth_exceptions
from google.auth import jwt as google_jwt

from app.core.config import settings
from app.core.security import AccountStatus, account_status_cache

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient

PROJECT_ID = "activequeue-token-tests"
ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"
KID = "test-signing-key"
ROUTE = "/api/v1/activities"


def _private_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _certificate_pem(key: rsa.RSAPrivateKey) -> str:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.test")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


_SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_CERT_PEM = _certificate_pem(_SIGNING_KEY)


def _claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": PROJECT_ID,
        "auth_time": now - 60,
        "iat": now - 60,
        "exp": now + 3540,
        "sub": "token-user",
        "user_id": "token-user",
        "email": "token-user@example.com",
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _sign(
    claims: dict[str, Any], key: rsa.RSAPrivateKey = _SIGNING_KEY, kid: str | None = KID
) -> str:
    signer = crypt.RSASigner.from_string(_private_pem(key), key_id=kid)
    return google_jwt.encode(signer, claims).decode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unsigned(claims: dict[str, Any]) -> str:
    header = _b64(json.dumps({"alg": "none", "typ": "JWT", "kid": KID}).encode())
    return f"{header}.{_b64(json.dumps(claims).encode())}."


def _hs256_with_public_cert(claims: dict[str, Any]) -> str:
    """Algorithm confusion: an HMAC signed with the public certificate as the secret."""
    import hashlib
    import hmac

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
    body = _b64(json.dumps(claims).encode())
    mac = hmac.new(_CERT_PEM.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(mac)}"


def _tampered(claims: dict[str, Any]) -> str:
    """A validly signed token whose payload is swapped for another user's afterwards."""
    header, _, signature = _sign(claims).split(".")
    forged = _b64(json.dumps({**claims, "sub": "victim", "user_id": "victim"}).encode())
    return f"{header}.{forged}.{signature}"


class _AnonymousCredential(credentials.Base):
    """Token verification needs only the project ID; never look up real credentials."""

    def get_credential(self) -> google_credentials.Credentials:
        return google_credentials.AnonymousCredentials()  # type: ignore[no-untyped-call]


@pytest.fixture(autouse=True)
def production_verifier(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run firebase_admin outside emulator mode against our fake certificate endpoint."""
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    monkeypatch.setattr(settings, "firebase_auth_emulator_host", None)
    monkeypatch.setattr(google.oauth2.id_token, "_fetch_certs", lambda *_a: {KID: _CERT_PEM})

    with contextlib.suppress(ValueError):
        firebase_admin.delete_app(firebase_admin.get_app())
    firebase_admin.initialize_app(_AnonymousCredential(), options={"projectId": PROJECT_ID})
    yield
    firebase_admin.delete_app(firebase_admin.get_app())


async def _get(client: AsyncClient, token: str) -> tuple[int, str]:
    resp = await client.get(ROUTE, headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    return resp.status_code, body["error"]["code"] if resp.status_code >= 400 else "OK"


async def test_well_formed_signed_token_is_accepted(client: AsyncClient) -> None:
    assert await _get(client, _sign(_claims())) == (200, "OK")


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        pytest.param(
            _sign(_claims(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)),
            "AUTH_TOKEN_EXPIRED",
            id="expired",
        ),
        pytest.param(_sign(_claims(aud="someone-elses-project")), "AUTH_TOKEN_INVALID", id="aud"),
        pytest.param(
            _sign(_claims(aud=auth._token_gen.FIREBASE_AUDIENCE)),
            "AUTH_TOKEN_INVALID",
            id="custom-token-audience",
        ),
        pytest.param(
            _sign(_claims(iss="https://securetoken.google.com/someone-else")),
            "AUTH_TOKEN_INVALID",
            id="iss",
        ),
        pytest.param(_unsigned(_claims()), "AUTH_TOKEN_INVALID", id="alg-none"),
        pytest.param(_hs256_with_public_cert(_claims()), "AUTH_TOKEN_INVALID", id="alg-hs256"),
        pytest.param(_sign(_claims(), key=_OTHER_KEY), "AUTH_TOKEN_INVALID", id="wrong-key"),
        pytest.param(_sign(_claims(), kid="unknown-kid"), "AUTH_TOKEN_INVALID", id="unknown-kid"),
        pytest.param(_sign(_claims(), kid=None), "AUTH_TOKEN_INVALID", id="no-kid"),
        pytest.param(_tampered(_claims()), "AUTH_TOKEN_INVALID", id="tampered-payload"),
        pytest.param(
            _sign(_claims(iat=int(time.time()) + 600)), "AUTH_TOKEN_INVALID", id="iat-in-future"
        ),
        pytest.param(_sign(_claims(sub="")), "AUTH_TOKEN_INVALID", id="empty-sub"),
        pytest.param(_sign(_claims(sub=None)), "AUTH_TOKEN_INVALID", id="missing-sub"),
        pytest.param(_sign(_claims(sub="u" * 129)), "AUTH_TOKEN_INVALID", id="sub-too-long"),
        pytest.param("a.b", "AUTH_TOKEN_INVALID", id="not-a-jwt"),
    ],
)
async def test_bad_tokens_are_rejected(client: AsyncClient, token: str, expected: str) -> None:
    assert await _get(client, token) == (401, expected)


@pytest.mark.parametrize(
    "header",
    [
        f"Basic {_sign(_claims())}",
        _sign(_claims()),
        "Bearer ",
    ],
    ids=["basic-scheme", "no-scheme", "empty-bearer"],
)
async def test_token_only_accepted_as_a_bearer_credential(
    client: AsyncClient, header: str
) -> None:
    resp = await client.get(ROUTE, headers={"Authorization": header})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_MISSING"


async def test_token_outside_the_authorization_header_is_ignored(client: AsyncClient) -> None:
    token = _sign(_claims())
    resp = await client.get(f"{ROUTE}?access_token={token}", cookies={"token": token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_MISSING"


async def test_certificate_fetch_failure_is_401_not_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _unreachable(*_a: Any) -> dict[str, str]:
        raise google_auth_exceptions.TransportError("certs endpoint unreachable")

    monkeypatch.setattr(google.oauth2.id_token, "_fetch_certs", _unreachable)
    assert await _get(client, _sign(_claims())) == (401, "AUTH_TOKEN_INVALID")


# ---------------------------------------------------------------------------
# Revocation and Firebase-side disabling (the user record behind a valid token)
# ---------------------------------------------------------------------------


def _record(status: AccountStatus | Exception, calls: list[str]) -> Any:
    async def _fetch(uid: str) -> AccountStatus:
        calls.append(uid)
        if isinstance(status, Exception):
            raise status
        return status

    return _fetch


async def test_token_issued_before_a_revoke_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    issued = int(time.time()) - 120
    revoked_at_ms = (issued + 60) * 1000
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(AccountStatus(disabled=False, tokens_valid_after_ms=revoked_at_ms), []),
    )

    assert await _get(client, _sign(_claims(iat=issued, auth_time=issued))) == (
        401,
        "AUTH_TOKEN_INVALID",
    )
    # A token minted after the revoke (the client signed in again) is fine.
    assert await _get(client, _sign(_claims())) == (200, "OK")


async def test_firebase_disabled_user_is_403(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(AccountStatus(disabled=True, tokens_valid_after_ms=0), []),
    )
    assert await _get(client, _sign(_claims())) == (403, "ACCOUNT_DISABLED")


async def test_deleted_firebase_user_is_401(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(auth.UserNotFoundError("no user record"), []),
    )
    assert await _get(client, _sign(_claims())) == (401, "AUTH_TOKEN_INVALID")


async def test_user_record_is_cached_per_uid(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(AccountStatus(disabled=False, tokens_valid_after_ms=0), calls),
    )
    for _ in range(3):
        assert await _get(client, _sign(_claims())) == (200, "OK")
    assert calls == ["token-user"]
    assert account_status_cache.get("token-user") is not None


async def test_identity_toolkit_outage_fails_open_and_is_not_cached(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(UnavailableError("identity toolkit down"), calls),
    )
    assert await _get(client, _sign(_claims())) == (200, "OK")
    assert await _get(client, _sign(_claims())) == (200, "OK")
    assert calls == ["token-user", "token-user"]
    assert account_status_cache.get("token-user") is None


async def test_bad_signature_never_reaches_the_user_record_lookup(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.core.security.fetch_account_status",
        _record(AccountStatus(disabled=False, tokens_valid_after_ms=0), calls),
    )
    assert await _get(client, _tampered(_claims())) == (401, "AUTH_TOKEN_INVALID")
    assert calls == []
