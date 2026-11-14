"""The committed OpenAPI document must match what the app generates.

`contracts/openapi.json` is the provider contract: the provider replay suite validates
real responses against it, the frontend derives its compile-time contract types from it,
and CI diffs it against `main` for breaking changes (oasdiff). Committing it means every
API change shows up as a reviewable diff.

Regenerate after an intentional API change with `make contracts`.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import ERROR_CODES
from app.main import app
from tests.contract.paths import OPENAPI_PATH, UPDATE


def generate_openapi() -> dict[str, Any]:
    app.openapi_schema = None  # never reuse a schema cached while other tests mutated routes
    return app.openapi()


def render_openapi() -> str:
    return json.dumps(generate_openapi(), indent=2, sort_keys=True) + "\n"


def test_committed_openapi_matches_app() -> None:
    rendered = render_openapi()
    if UPDATE:
        OPENAPI_PATH.write_text(rendered)
    assert OPENAPI_PATH.exists(), "contracts/openapi.json is missing; run `make contracts`"
    assert OPENAPI_PATH.read_text() == rendered, (
        "contracts/openapi.json is stale. If the API change is intentional, run "
        "`make contracts` and commit the result."
    )


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method.upper(), path, op)
        for path, item in spec["paths"].items()
        for method, op in item.items()
    ]


def test_every_success_response_documents_a_typed_body() -> None:
    """No endpoint may fall back to an untyped `{}` success schema."""
    spec = generate_openapi()
    for method, path, op in _operations(spec):
        ok = next(code for code in op["responses"] if code.startswith("2"))
        schema = op["responses"][ok]["content"]["application/json"]["schema"]
        assert "$ref" in schema, f"{method} {path} {ok} has no typed response model"


def test_api_routes_document_the_error_envelope_not_fastapis_default() -> None:
    spec = generate_openapi()
    statuses = {str(s) for s in ERROR_CODES.values()}
    for method, path, op in _operations(spec):
        if not path.startswith("/api/v1"):
            continue
        assert statuses <= op["responses"].keys(), f"{method} {path} misses error statuses"
        for status in statuses:
            ref = op["responses"][status]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorEnvelope"), f"{method} {path} {status} -> {ref}"
    assert "HTTPValidationError" not in spec["components"]["schemas"]
