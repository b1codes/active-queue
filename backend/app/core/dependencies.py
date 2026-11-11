from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Path
from pydantic import AfterValidator, Field

from app.core.firestore import get_firestore_client
from app.core.sanitizer import DOCUMENT_ID_PATTERN, is_valid_document_id

if TYPE_CHECKING:
    from collections.abc import Generator

    from google.cloud.firestore import AsyncClient


def _check_document_id(value: str) -> str:
    if not is_valid_document_id(value):
        msg = "must be a valid ID (letters, digits, '_', '-', '.', ':'; not reserved)"
        raise ValueError(msg)
    return value


# The contract states the rule as a pattern; the validator enforces it (Pydantic's Rust regex
# engine has no lookahead, so the pattern is schema-only).
_DOCUMENT_ID_SCHEMA = {"pattern": DOCUMENT_ID_PATTERN}

# Path parameter that is interpolated into a Firestore document path. Invalid IDs
# (reserved __x__, ".", "..") become 400 VALIDATION_FAILED instead of a 500.
DocumentIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200, json_schema_extra=_DOCUMENT_ID_SCHEMA),
    AfterValidator(_check_document_id),
]

# The same rule for an ID in a request body. IDs are only ever ones the API handed out, so
# an invalid one is rejected rather than rewritten into a different ID.
DocumentId = Annotated[
    str,
    Field(min_length=1, max_length=200, json_schema_extra=_DOCUMENT_ID_SCHEMA),
    AfterValidator(_check_document_id),
]

# A catalog activity ID: the same rule, shorter. (A Field on the attribute can't lower an
# Annotated max_length; the contract kept the inner one.)
ActivityId = Annotated[
    str,
    Field(min_length=1, max_length=100, json_schema_extra=_DOCUMENT_ID_SCHEMA),
    AfterValidator(_check_document_id),
]


def get_db() -> Generator[AsyncClient, None, None]:
    """FastAPI dependency yielding Firestore AsyncClient."""
    yield get_firestore_client()
