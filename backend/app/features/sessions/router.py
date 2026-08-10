from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Path, Query, status


from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.activities.service import ActivityService
from app.features.content.repository import ContentRepository
from app.features.sessions.repository import SessionRepository
from app.features.sessions.schemas import (
    CompleteSessionRequest,
    CreateSessionRequest,
    SessionListResponse,
    SessionSchema,
)
from app.features.sessions.service import SessionService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service(db: AsyncClient = Depends(get_db)) -> SessionService:
    """Dependency injector for SessionService."""
    session_repo = SessionRepository(db)
    content_repo = ContentRepository(db)
    activity_service = ActivityService()
    return SessionService(session_repo, activity_service, content_repo)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Get user workout sessions history",
    description="Fetch paginated workout session history for authenticated user per SPEC §9.5.",
)
async def get_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    status_filter: str | None = Query(None, alias="status", max_length=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """GET /api/v1/sessions history list endpoint."""
    list_resp: SessionListResponse = await service.get_user_sessions(
        user_id=current_user.uid,
        limit=limit,
        cursor=cursor,
        status_filter=status_filter,
    )
    return success_response(list_resp.model_dump())


@router.get(
    "/active",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Get user active session",
    description="Fetch current non-terminal active session for authenticated user with lazy abandonment evaluation per SPEC §7.2.",
)
async def get_active_session(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any] | None]:
    """GET /api/v1/sessions/active endpoint."""
    session = await service.get_active_session(current_user.uid)
    data = SessionSchema.from_domain(session).model_dump() if session else None
    return success_response(data)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    summary="Create a workout session",
    description="Create a new pending workout time-boxing session per SPEC §7.1 & §9.5.",
)
async def create_session(
    body: CreateSessionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/sessions endpoint."""
    session = await service.create_session(
        user_id=current_user.uid,
        activity_id=body.activity_id,
        match_mode=body.match_mode,
        content_id=body.content_id,
        target_duration_seconds=body.target_duration_seconds,
    )
    return success_response(SessionSchema.from_domain(session).model_dump())


@router.post(
    "/{session_id}/start",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Start a workout session",
    description="Start a pending workout session (idempotent) per SPEC §7.1 & §9.5.",
)
async def start_session(
    session_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/sessions/{session_id}/start endpoint."""
    session = await service.start_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(SessionSchema.from_domain(session).model_dump())


@router.post(
    "/{session_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Complete a workout session",
    description="Atomically complete a workout session, set feed item consumed, and arrayUnion content ID per SPEC §7.1 & §9.6.",
)
async def complete_session(
    session_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    body: CompleteSessionRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/sessions/{session_id}/complete endpoint."""
    ext_url = body.external_workout_url if body else None
    hk_uuid = body.healthkit_uuid if body else None

    session = await service.complete_session(
        user_id=current_user.uid,
        session_id=session_id,
        external_workout_url=ext_url,
        healthkit_uuid=hk_uuid,
    )
    return success_response(SessionSchema.from_domain(session).model_dump())


@router.post(
    "/{session_id}/abandon",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Abandon a workout session",
    description="Explicitly abandon a workout session per SPEC §7.1 & §9.5.",
)
async def abandon_session(
    session_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/sessions/{session_id}/abandon endpoint."""
    session = await service.abandon_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(SessionSchema.from_domain(session).model_dump())


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="Discard a created session",
    description="Hard delete a pending session per Decision #6 & SPEC §9.5.",
)
async def discard_session(
    session_id: str = Path(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-\.:/]+$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """DELETE /api/v1/sessions/{session_id} discard endpoint."""
    res = await service.discard_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(res)
