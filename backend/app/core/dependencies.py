from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Path
from pydantic import AfterValidator

from app.core.firestore import get_firestore_client
from app.core.sanitizer import is_valid_document_id

if TYPE_CHECKING:
    from collections.abc import Generator

    from google.cloud.firestore import AsyncClient


def _check_document_id(value: str) -> str:
    if not is_valid_document_id(value):
        msg = "must be a valid ID (letters, digits, '_', '-', '.', ':'; not reserved)"
        raise ValueError(msg)
    return value


# Path parameter that is interpolated into a Firestore document path. Invalid IDs
# (reserved __x__, ".", "..") become 400 VALIDATION_FAILED instead of a 500.
DocumentIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200),
    AfterValidator(_check_document_id),
]


def get_db() -> Generator[AsyncClient, None, None]:
    """FastAPI dependency yielding Firestore AsyncClient."""
    yield get_firestore_client()
