"""Static checks on contracts/interactions/ (no emulator needed).

The emulator tier proves the provider produces these responses; these tests prove the
contract files themselves are complete and self-consistent:

* every interaction targets a documented operation and status, and its example body
  satisfies the strict OpenAPI schema (so the frontend consumer suite only ever
  replays shapes the server can actually send);
* every operation in contracts/openapi.json has at least one interaction;
* every error code in an example, and every code the backend can raise, is registered
  in ERROR_CODES with the status the example shows.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from app.core.errors import ERROR_CODES
from tests.contract.interactions import (
    AUTH_MODES,
    Interaction,
    load_interactions,
    openapi,
    operation_for,
    schema_errors,
)

INTERACTIONS = load_interactions()
APP_DIR = Path(__file__).resolve().parents[2] / "app"

# Transport-level codes produced outside AppError (middleware/errors.py, /healthz).
# They are not part of ERROR_CODES because their status is not fixed by the code.
FALLBACK_CODES = {"HTTP_ERROR", "NOT_FOUND", "SERVICE_UNAVAILABLE"}


def test_interaction_ids_are_unique() -> None:
    dupes = [i for i, n in Counter(it.id for it in INTERACTIONS).items() if n > 1]
    assert not dupes, f"duplicate interaction ids: {dupes}"


@pytest.mark.parametrize("it", INTERACTIONS, ids=lambda it: it.id)
def test_interaction_is_well_formed(it: Interaction) -> None:
    assert it.auth in AUTH_MODES, f"{it.id}: unknown auth mode {it.auth!r}"
    assert it.response_body is not None, (
        f"{it.id}: no recorded example; run `UPDATE_CONTRACTS=1 make test-backend`"
    )
    consumers = it.raw.get("consumers")
    assert isinstance(consumers, list), f"{it.id}: `consumers` must be a list"
    if not consumers:
        assert it.raw.get("consumer_note"), f"{it.id}: say why no app code consumes this"


@pytest.mark.parametrize("it", INTERACTIONS, ids=lambda it: it.id)
def test_example_satisfies_strict_schema(it: Interaction) -> None:
    errors = schema_errors(it.method, it.path, it.status, it.response_body)
    assert not errors, f"{it.id} example violates contracts/openapi.json:\n" + "\n".join(errors)


def test_every_operation_has_an_interaction() -> None:
    covered = {(it.method.lower(), operation_for(it.method, it.path)[0]) for it in INTERACTIONS}
    missing = sorted(
        f"{method.upper()} {path}"
        for path, item in openapi()["paths"].items()
        for method in item
        if (method, path) not in covered
    )
    assert not missing, f"operations without a contract interaction: {missing}"


@pytest.mark.parametrize(
    "it", [it for it in INTERACTIONS if it.status >= 400], ids=lambda it: it.id
)
def test_error_examples_use_registered_codes(it: Interaction) -> None:
    code = it.response_body["error"]["code"]
    assert code in ERROR_CODES, f"{it.id}: {code} is not in app/core/errors.py ERROR_CODES"
    assert ERROR_CODES[code] == it.status, f"{it.id}: {code} is {ERROR_CODES[code]} in ERROR_CODES"


def test_every_raised_code_is_registered() -> None:
    """A code missing from ERROR_CODES is invisible in OpenAPI and may get the wrong status."""
    pattern = re.compile(r"""code\s*=\s*["']([A-Z][A-Z0-9_]+)["']""")
    raised = {
        (code, path.relative_to(APP_DIR.parent).as_posix())
        for path in APP_DIR.rglob("*.py")
        for code in pattern.findall(path.read_text())
    }
    unregistered = sorted(
        f"{code} ({where})"
        for code, where in raised
        if code not in ERROR_CODES and code not in FALLBACK_CODES
    )
    assert not unregistered, f"codes raised but not in ERROR_CODES: {unregistered}"
