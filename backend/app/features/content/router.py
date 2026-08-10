from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.content.repository import SourceRepository
from app.features.content.schemas import CreateSourceRequest, SourceSchema
from app.features.content.service import ContentService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

router = APIRouter(prefix="/sources", tags=["sources"])


def get_content_service(db: AsyncClient = Depends(get_db)) -> ContentService:
    """Dependency injector for ContentService."""
    source_repo = SourceRepository(db)
    return ContentService(source_repo)


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
