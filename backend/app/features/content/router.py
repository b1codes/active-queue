from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.content.repository import ContentRepository, SourceRepository
from app.features.content.schemas import CreateSourceRequest, SourceSchema, SyncResponse
from app.features.content.service import ContentService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

router = APIRouter(prefix="/sources", tags=["sources"])


def get_content_service(db: AsyncClient = Depends(get_db)) -> ContentService:
    """Dependency injector for ContentService."""
    source_repo = SourceRepository(db)
    content_repo = ContentRepository(db)
    return ContentService(source_repo, content_repo)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    summary="Add content source",
    description="Add a YouTube playlist or channel URL/ID as a content source per SPEC §9.3.",
)
async def create_source(
    body: CreateSourceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """Add content source endpoint."""
    source = await service.add_source(current_user.uid, body.url_or_id)
    return success_response(SourceSchema.from_domain(source).model_dump())


@router.post(
    "/{source_id}/sync",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Trigger source sync chunk",
    description="Process one chunk (<= 5 pages / ~250 items) of resumable sync per SPEC §9.4.",
)
async def sync_source_chunk(
    source_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """Trigger chunked resumable sync endpoint."""
    sync_resp: SyncResponse = await service.sync_source_chunk(current_user.uid, source_id)
    return success_response(sync_resp.model_dump())
