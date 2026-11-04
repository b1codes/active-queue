from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Path
from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.core.firestore import get_firestore_client
from app.core.sanitizer import is_valid_document_id, sanitize_identifier

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


class PaginationParams(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    cursor: str | None = Field(None, max_length=200)

    @field_validator("cursor")
    @classmethod
    def sanitize_cur(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_identifier(v, max_length=200)
