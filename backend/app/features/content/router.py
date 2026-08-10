from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Path, Query, status


from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.content.repository import ContentRepository, SourceRepository
from app.features.content.schemas import (
    ContentMatchRequest,
    ContentMatchResponse,
    CreateSourceRequest,
    FeedResponse,
    SourceSchema,
    SyncResponse,
    TimeMatchRequest,
    TimeMatchResponse,
)
from app.features.content.service import ContentService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

router = APIRouter(tags=["content"])


def get_content_service(db: AsyncClient = Depends(get_db)) -> ContentService:
    """Dependency injector for ContentService."""
    source_repo = SourceRepository(db)
    content_repo = ContentRepository(db)
    return ContentService(source_repo, content_repo)


# Sources endpoints
@router.post(
    "/sources",
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
    "/sources/{source_id}/sync",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Trigger source sync chunk",
    description="Process one chunk (<= 5 pages / ~250 items) of resumable sync per SPEC §9.4.",
)
async def sync_source_chunk(
    source_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """Trigger chunked resumable sync endpoint."""
    sync_resp: SyncResponse = await service.sync_source_chunk(current_user.uid, source_id)
    return success_response(sync_resp.model_dump())


# Feed endpoints
@router.get(
    "/content/feed",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Get user content feed",
    description="Fetch user unconsumed feed items with cursor pagination, duration filters, and server duration_label per SPEC §9.2.",
)
async def get_user_feed(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    min_duration: int | None = Query(None, ge=0, le=86400),
    max_duration: int | None = Query(None, ge=0, le=86400),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """GET /api/v1/content/feed endpoint."""
    feed_resp: FeedResponse = await service.get_user_feed(
        user_id=current_user.uid,
        limit=limit,
        cursor=cursor,
        min_duration=min_duration,
        max_duration=max_duration,
    )
    return success_response(feed_resp.model_dump())


@router.post(
    "/content/feed/{content_id}/hide",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Manually hide feed item",
    description="Mark feed item as consumed and update user consumed_content for media consumed outside a workout per SPEC §9.1 & §9.2.",
)
async def hide_feed_item(
    content_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/content/feed/{content_id}/hide endpoint."""
    res = await service.hide_feed_item(current_user.uid, content_id)
    return success_response(res)


# Content Matching endpoint
@router.post(
    "/content/match",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Match content item to physical activity catalog",
    description="Match content item by content_id against activity catalog with distinct rejection reasons per SPEC §5.2 & §9.6.",
)
async def match_content(
    body: ContentMatchRequest,
    _current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/content/match endpoint."""
    match_resp: ContentMatchResponse = await service.match_content(body.content_id)
    return success_response(match_resp.model_dump())


# Time-First Matching endpoint
@router.post(
    "/content/match-time",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Match time block duration to candidate feed items",
    description="Match target time block duration against unconsumed feed items using asymmetric primary [B, B+300] and fallback [B-120, B) windows per SPEC §5.3 & §9.6.",
)
async def match_time_block(
    body: TimeMatchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ContentService = Depends(get_content_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/content/match-time endpoint."""
    match_resp: TimeMatchResponse = await service.match_time_block(
        current_user.uid, body.target_duration_seconds
    )
    return success_response(match_resp.model_dump())
