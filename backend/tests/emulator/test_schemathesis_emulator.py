"""Schemathesis property-based fuzzing of every operation in contracts/openapi.json.

Schemathesis generates requests from the committed contract, valid ones and invalid ones,
and sends each to the real app on the emulators as a signed-in user. Every response must:

- not be a 5xx, except the 501 FEATURE_NOT_AVAILABLE that SPEC §9.7 specifies for
  v1.1 fields (its body must still match the contract),
- use a status code, content type, headers and body the contract documents for it,
- accept data the contract says is valid, and reject data it says is invalid,
- still need the token: Schemathesis resends requests without it and with a wrong one,
- answer undeclared methods with 405 and an accurate `Allow` header.

The contract is the committed snapshot rather than the live app's schema, so the fuzzer
holds the app to what the mobile client was built against. test_openapi_snapshot.py
keeps the two identical.

The app runs under uvicorn on a loopback port, not through ASGITransport, because those
auth and method checks send probe requests of their own over HTTP.

PR runs are derandomized and short. The nightly run (fuzz-nightly.yml) sets
FUZZ_MAX_EXAMPLES higher and passes a fresh `--hypothesis-seed`, which it logs, so a
failure reproduces locally with:

    make fuzz-api SEED=<seed> FUZZ_MAX_EXAMPLES=<n>
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonschema
import pytest
import schemathesis
import uvicorn
from hypothesis import HealthCheck, settings
from schemathesis.checks import (
    allow_header_conformance,
    negative_data_rejection,
    not_a_server_error,
    positive_data_acceptance,
)

from app.core.config import settings as app_settings
from app.main import app

if TYPE_CHECKING:
    from collections.abc import Iterator

    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient

    from tests.emulator.conftest import EmulatorUser

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"
MAX_EXAMPLES = int(os.environ.get("FUZZ_MAX_EXAMPLES", "25"))
NIGHTLY = "FUZZ_MAX_EXAMPLES" in os.environ

CONTRACT_DOC = json.loads(CONTRACT.read_text())
schema = schemathesis.openapi.from_path(CONTRACT)
# Keep the bearer token readable in failure output; it is an emulator-only token.
schema.config.output.sanitization.update(enabled=False)
schema.config.generation.update(
    # Every request carries alice's real token. The ignored_auth check still resends each
    # one without a token and with a bad one.
    with_security_parameters=False,
    # FastAPI ignores query parameters a route doesn't declare, and OpenAPI can't state
    # otherwise, so an unknown `?x=1` being accepted is not a contract violation.
    allow_extra_parameters=False,
)

# 400 VALIDATION_FAILED means the input broke a rule the schema can state, so the contract
# must state it. These 422 codes are domain rules no schema can state (whether a string
# names a real playlist), so a schema-valid request may still get one.
DOMAIN_REJECTIONS = {"SOURCE_URL_UNPARSEABLE"}

# Free-text fields the sanitizer may empty out (whitespace, control characters or markup
# only), which is a 400 on that field alone. No schema can state "has visible text once
# HTML is stripped". Seen with seed 3703408288.
SANITIZED_TEXT_FIELDS = {"url_or_id"}

# A literal path segment that a templated route also matches. `Allow` truthfully lists the
# templated route's methods too, which the contract doesn't document for the literal path.
SHADOWED_PATHS = {
    # DELETE /sessions/{session_id} routes "active" as an ID; it is a 404 (session IDs are
    # Firestore auto-IDs) and never deletes anything.
    "/api/v1/sessions/active",
}


@pytest.fixture(autouse=True)
def _no_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """One user sends hundreds of requests here; rate limiting has its own suite."""
    for name in ("rate_limit_general", "rate_limit_sync", "rate_limit_heavy", "rate_limit_ip"):
        monkeypatch.setattr(app_settings, name, 1_000_000)


@pytest.fixture
def live_api(db: FirestoreAsyncClient) -> Iterator[str]:
    """The real app under uvicorn on a free loopback port, against the wiped emulators.

    Its lifespan opens a Firestore client on the server's own event loop, so nothing is
    shared with the test's loop.
    """
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="on", log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            pytest.fail("uvicorn did not start")
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def _error_code(response: Any) -> str | None:
    if response.status_code < 400:
        return None
    code: str | None = response.json()["error"]["code"]
    return code


def _sanitized_away(response: Any) -> bool:
    if response.status_code != 400 or _error_code(response) != "VALIDATION_FAILED":
        return False
    fields = {d["field"] for d in response.json()["error"]["details"]}
    return bool(fields) and fields <= SANITIZED_TEXT_FIELDS


def _wire_query_is_valid(case: Any) -> bool:
    """Whether a "negative" GET query is actually valid once it is on the wire.

    A query string can't tell `[0.0]` from `0`: a one-element array encodes like a scalar,
    and 0.0 is an integer in JSON Schema. Schemathesis counts such a mutation as invalid
    and expects a 4xx, though the request it sends is valid. Seen with seed 3703408288
    (`?min_duration=0.0&max_duration=0.0`).
    """
    operation = CONTRACT_DOC["paths"][case.operation.path][case.method.lower()]
    parameters = operation.get("parameters", [])
    if case.method != "GET" or any(p["in"] != "query" for p in parameters):
        return False
    schemas = {p["name"]: p["schema"] for p in parameters}
    for name, value in (case.query or {}).items():
        if name not in schemas:
            return False
        wire = value[0] if isinstance(value, list) and len(value) == 1 else value
        if isinstance(wire, float) and wire.is_integer():
            wire = int(wire)
        try:
            jsonschema.validate(wire, schemas[name])
        except jsonschema.ValidationError:
            return False
    return True


def _excluded_checks(case: Any, response: Any) -> list[Any]:
    code = _error_code(response)
    excluded = []
    if response.status_code == 501 and code == "FEATURE_NOT_AVAILABLE":
        excluded.append(not_a_server_error)
    if (response.status_code == 422 and code in DOMAIN_REJECTIONS) or _sanitized_away(response):
        excluded.append(positive_data_acceptance)
    if case.operation.path in SHADOWED_PATHS:
        excluded.append(allow_header_conformance)
    if response.status_code < 300 and _wire_query_is_valid(case):
        excluded.append(negative_data_rejection)
    return excluded


@schema.parametrize()
@settings(
    max_examples=MAX_EXAMPLES,
    derandomize=not NIGHTLY,
    deadline=None,
    database=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
    ],
)
def test_every_operation_honours_the_contract(
    case: Any, live_api: str, alice: EmulatorUser
) -> None:
    response = case.call(base_url=live_api, headers=alice.headers)
    case.validate_response(
        response,
        headers=alice.headers,
        excluded_checks=_excluded_checks(case, response),
        transport_kwargs={"base_url": live_api, "headers": alice.headers},
    )
