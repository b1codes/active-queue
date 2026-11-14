"""Nightly: Firebase's ID-token signing certificates still have the shape firebase_admin expects.

No credentials needed. ID-token claim shapes are checked on every PR against tokens the
Auth emulator mints (tests/emulator/test_contract_firebase_token.py). This covers the
part the emulator skips: production signature verification material.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import httpx
from cryptography import x509

from tests.contract.paths import THIRD_PARTY_DIR
from tests.contract.test_third_party_recorded import errors_for
from tests.contract.thirdparty.conftest import LIVE


def _cert_uri() -> str:
    schema = json.loads((THIRD_PARTY_DIR / "firebase" / "x509_certs.schema.json").read_text())
    match = re.search(
        r"https://\S+?securetoken@system\.gserviceaccount\.com", schema["description"]
    )
    assert match
    return match.group(0)


async def test_signing_certificates() -> None:
    assert LIVE
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_cert_uri())
    assert resp.status_code == 200, resp.text

    errors = errors_for("firebase/x509_certs", resp.json())
    assert not errors, "\n".join(errors)

    now = datetime.now(UTC)
    for kid, pem in resp.json().items():
        cert = x509.load_pem_x509_certificate(pem.encode())
        assert cert.not_valid_before_utc <= now <= cert.not_valid_after_utc, f"{kid} not current"

    # firebase_admin caches the certificates for max-age; without it every request refetches.
    assert re.search(r"max-age=\d+", resp.headers.get("cache-control", "")), resp.headers
