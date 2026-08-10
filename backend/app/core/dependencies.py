from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from app.core.firestore import get_firestore_client
from app.core.sanitizer import sanitize_identifier

if TYPE_CHECKING:
    from collections.abc import Generator

    from google.cloud.firestore import AsyncClient


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

