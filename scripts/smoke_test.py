#!/usr/bin/env python3
"""Post-deploy smoke check for the ActiveQueue API (ClickUp 86bcxrv0z).

Runs a handful of real requests against a running API and exits non-zero if any fails:

1. GET /health returns 200 with Firestore up. The check retries for --wait seconds to
   ride out a cold start. It uses /health because Cloud Run never routes /healthz.
2. GET /api/v1/users/me without a token returns 401.
3. GET /api/v1/users/me with a real ID token returns 200 for the smoke user.
4. GET /api/v1/activities returns a non-empty catalog.
5. With --expect-verified-tokens, a forged ID token for the smoke user (valid claims,
   bad signature) returns 401. This catches a deployed env that skips signature checks,
   for example one that booted in Auth-emulator mode.

How it gets the ID token. Both paths sign in with a Firebase custom token for --uid
through Identity Toolkit's signInWithCustomToken, the same way the app signs in:

  --auth emulator       The Auth emulator accepts an unsigned custom token. Used in CI
                        against the built container (see the `container` job in ci.yml).
  --auth custom-token   `gcloud iam service-accounts sign-jwt` signs it as --signer.
                        The caller needs roles/iam.serviceAccountTokenCreator on that
                        service account, and --firebase-api-key must be the project's
                        Web API key. Used by scripts/deploy.sh after each deploy.

The script needs only the Python standard library (and gcloud for --auth custom-token).
"""

# ruff: noqa: T201 - a CLI; printing each check is its output

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

# The audience Identity Toolkit requires on a custom token (a URL, not a secret).
CUSTOM_TOKEN_AUDIENCE = (
    "https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit"  # noqa: S105
)


class SmokeError(Exception):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _jwt(header: dict[str, Any], claims: dict[str, Any], signature: bytes = b"") -> str:
    parts = [_b64url(json.dumps(header).encode()), _b64url(json.dumps(claims).encode())]
    return ".".join([*parts, _b64url(signature)])


def request(
    method: str, url: str, token: str | None = None, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json", "User-Agent": "activequeue-smoke-test"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - URL is ours
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"_raw": raw[:300].decode(errors="replace")}
    return status, payload


# --- ID tokens ----------------------------------------------------------------------------


def _custom_token_claims(uid: str, issuer: str) -> dict[str, Any]:
    now = int(time.time())
    return {
        "iss": issuer,
        "sub": issuer,
        "aud": CUSTOM_TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "uid": uid,
    }


def _exchange_custom_token(identity_toolkit: str, api_key: str, custom_token: str) -> str:
    status, body = request(
        "POST",
        f"{identity_toolkit}/v1/accounts:signInWithCustomToken?key={api_key}",
        body={"token": custom_token, "returnSecureToken": True},
    )
    if status != 200 or "idToken" not in body:
        raise SmokeError(f"signInWithCustomToken returned {status}: {body}")
    return str(body["idToken"])


def emulator_id_token(auth_emulator_host: str, uid: str) -> str:
    claims = _custom_token_claims(uid, "firebase-auth-emulator@example.com")
    unsigned = _jwt({"alg": "none", "typ": "JWT"}, claims)
    return _exchange_custom_token(
        f"http://{auth_emulator_host}/identitytoolkit.googleapis.com", "fake-api-key", unsigned
    )


def signed_id_token(signer: str, api_key: str, uid: str) -> str:
    claims = _custom_token_claims(uid, signer)
    with tempfile.TemporaryDirectory() as tmp:
        claims_path, out_path = os.path.join(tmp, "claims.json"), os.path.join(tmp, "token.jwt")
        with open(claims_path, "w") as f:
            json.dump(claims, f)
        subprocess.run(  # noqa: S603 - fixed argv, no shell
            [  # noqa: S607 - gcloud from PATH, as in deploy.sh
                "gcloud",
                "iam",
                "service-accounts",
                "sign-jwt",
                f"--iam-account={signer}",
                claims_path,
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(out_path) as f:
            custom_token = f.read().strip()
    return _exchange_custom_token("https://identitytoolkit.googleapis.com", api_key, custom_token)


def forged_id_token(project_id: str, uid: str) -> str:
    """Claims a real Firebase ID token would carry, with a signature nobody made."""
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{project_id}",
        "aud": project_id,
        "auth_time": now - 60,
        "user_id": uid,
        "sub": uid,
        "iat": now - 60,
        "exp": now + 3000,
        "firebase": {"identities": {}, "sign_in_provider": "custom"},
    }
    return _jwt(
        {"alg": "RS256", "kid": "smoke-test-forged", "typ": "JWT"}, claims, os.urandom(256)
    )


# --- Checks -------------------------------------------------------------------------------


def check_health(base: str, wait_seconds: float) -> str:
    deadline = time.monotonic() + wait_seconds
    last: tuple[int, Any] = (0, None)
    while True:
        try:
            status, body = request("GET", f"{base}/health")
            last = (status, body)
            data = body.get("data") or {}
            if status == 200 and data.get("status") == "healthy":
                if (data.get("firestore") or {}).get("status") != "up":
                    raise SmokeError(f"Firestore not up: {data}")
                return f"firestore {data['firestore'].get('latency_ms')} ms"
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = (0, repr(exc))
        if time.monotonic() >= deadline:
            raise SmokeError(f"not healthy after {wait_seconds:.0f}s; last: {last}")
        time.sleep(2)


def expect_status(method: str, url: str, token: str | None, want: int) -> dict[str, Any]:
    status, body = request(method, url, token)
    if status != want:
        raise SmokeError(f"{method} {url} returned {status}, expected {want}: {body}")
    return body


def run(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    api = f"{base}/api/v1"
    token: str | None = None
    failures = 0

    def step(name: str, fn: Callable[[], str | None]) -> None:
        nonlocal failures
        try:
            detail = fn()
        except (SmokeError, subprocess.CalledProcessError, OSError) as exc:
            failures += 1
            stderr = getattr(exc, "stderr", None)
            msg = stderr.decode(errors="replace").strip() if stderr else exc
            print(f"FAIL  {name}: {msg}", flush=True)
        else:
            print(f"ok    {name}" + (f" ({detail})" if detail else ""), flush=True)

    def get_token() -> str:
        nonlocal token
        if args.auth == "emulator":
            token = emulator_id_token(args.auth_emulator_host, args.uid)
        else:
            token = signed_id_token(args.signer, args.firebase_api_key, args.uid)
        return f"uid {args.uid}"

    def unauthenticated() -> None:
        expect_status("GET", f"{api}/users/me", None, 401)

    def forged() -> None:
        expect_status("GET", f"{api}/users/me", forged_id_token(args.project, args.uid), 401)

    def me() -> None:
        if token is None:
            raise SmokeError("no ID token (sign-in failed)")
        body = expect_status("GET", f"{api}/users/me", token, 200)
        uid = ((body.get("data") or {}).get("user") or {}).get("uid")
        if uid != args.uid:
            raise SmokeError(f"/users/me returned uid {uid!r}, expected {args.uid!r}")

    def activities() -> str:
        if token is None:
            raise SmokeError("no ID token (sign-in failed)")
        body = expect_status("GET", f"{api}/activities", token, 200)
        catalog = (body.get("data") or {}).get("activities") or []
        if not catalog:
            raise SmokeError("activities catalog is empty")
        return f"{len(catalog)} activities"

    step("GET /health", lambda: check_health(base, args.wait))
    step("GET /users/me without a token is 401", unauthenticated)
    step("sign in as the smoke user", get_token)
    step("GET /users/me", me)
    step("GET /activities", activities)
    if args.expect_verified_tokens:
        # After sign-in, so the forged token names an account that exists: a backend
        # that skips signature checks would then accept it.
        step("GET /users/me with a forged token is 401", forged)

    print(f"smoke test {'FAILED' if failures else 'passed'} against {base}", flush=True)
    return 1 if failures else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument(
        "base_url", help="API origin, e.g. https://activequeue-api-dev-xyz-uc.a.run.app"
    )
    p.add_argument("--auth", choices=["emulator", "custom-token"], default="custom-token")
    p.add_argument("--uid", default="smoke-test", help="uid of the smoke-test user")
    p.add_argument("--auth-emulator-host", default=os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"))
    p.add_argument("--signer", help="service account that signs the custom token")
    p.add_argument("--firebase-api-key", default=os.environ.get("FIREBASE_WEB_API_KEY"))
    p.add_argument("--project", help="GCP project ID (for --expect-verified-tokens)")
    p.add_argument("--expect-verified-tokens", action="store_true")
    p.add_argument("--wait", type=float, default=90.0, help="seconds to wait for /health")
    args = p.parse_args(argv)
    if args.auth == "emulator" and not args.auth_emulator_host:
        p.error("--auth emulator needs --auth-emulator-host or FIREBASE_AUTH_EMULATOR_HOST")
    if args.auth == "custom-token" and not (args.signer and args.firebase_api_key):
        p.error(
            "--auth custom-token needs --signer and --firebase-api-key (or FIREBASE_WEB_API_KEY)"
        )
    if args.expect_verified_tokens and not args.project:
        p.error("--expect-verified-tokens needs --project")
    return args


if __name__ == "__main__":
    sys.exit(run(parse_args()))
