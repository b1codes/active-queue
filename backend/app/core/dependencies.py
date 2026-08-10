from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.core.firestore import get_firestore_client

if TYPE_CHECKING:
    from collections.abc import Generator

    from google.cloud.firestore import AsyncClient


def get_db() -> Generator[AsyncClient, None, None]:
    """FastAPI dependency yielding Firestore AsyncClient."""
    yield get_firestore_client()


class PaginationParams(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
