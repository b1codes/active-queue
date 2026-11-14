from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import DocumentIdPath, get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser
from app.features.activities.service import ActivityService
from app.features.content.repository import ContentRepository
from app.features.sessions.repository import SessionRepository
from app.features.sessions.schemas import (
    CompleteSessionRequest,
    CreateSessionRequest,
    DiscardSessionResponse,
    SessionListResponse,
    SessionSchema,
)
from app.features.sessions.service import SessionService
from app.features.users.dependencies import get_authorized_user

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
    response_model=SuccessEnvelope[SessionListResponse],
    summary="Get user workout sessions history",
    description="Fetch paginated workout session history for authenticated user per SPEC §9.5.",
)
async def get_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=200),
    status_filter: str | None = Query(None, alias="status", max_length=50),
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionListResponse]:
    """GET /api/v1/sessions history list endpoint."""
    list_resp: SessionListResponse = await service.get_user_sessions(
        user_id=current_user.uid,
        limit=limit,
        cursor=cursor,
        status_filter=status_filter,
    )
    return success_response(list_resp)


@router.get(
    "/active",
    status_code=status.HTTP_200_OK,
    response_model=SuccessEnvelope[SessionSchema | None],
    summary="Get user active session",
    description="Fetch current non-terminal active session for authenticated user with lazy abandonment evaluation per SPEC §7.2.",
)
async def get_active_session(
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionSchema | None]:
    """GET /api/v1/sessions/active endpoint."""
    session = await service.get_active_session(current_user.uid)
    return success_response(SessionSchema.from_domain(session) if session else None)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessEnvelope[SessionSchema],
    summary="Create a workout session",
    description="Create a new pending workout time-boxing session per SPEC §7.1 & §9.5.",
)
async def create_session(
    body: CreateSessionRequest,
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionSchema]:
    """POST /api/v1/sessions endpoint."""
    session = await service.create_session(
        user_id=current_user.uid,
        activity_id=body.activity_id,
        match_mode=body.match_mode,
        content_id=body.content_id,
        target_duration_seconds=body.target_duration_seconds,
    )
    return success_response(SessionSchema.from_domain(session))


@router.post(
    "/{session_id}/start",
    status_code=status.HTTP_200_OK,
    response_model=SuccessEnvelope[SessionSchema],
    summary="Start a workout session",
    description="Start a pending workout session (idempotent) per SPEC §7.1 & §9.5.",
)
async def start_session(
    session_id: DocumentIdPath,
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionSchema]:
    """POST /api/v1/sessions/{session_id}/start endpoint."""
    session = await service.start_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(SessionSchema.from_domain(session))


@router.post(
    "/{session_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=SuccessEnvelope[SessionSchema],
    summary="Complete a workout session",
    description="Atomically complete a workout session, set feed item consumed, and arrayUnion content ID per SPEC §7.1 & §9.6.",
)
async def complete_session(
    session_id: DocumentIdPath,
    body: CompleteSessionRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionSchema]:
    """POST /api/v1/sessions/{session_id}/complete endpoint."""
    ext_url = body.external_workout_url if body else None
    hk_uuid = body.healthkit_uuid if body else None

    session = await service.complete_session(
        user_id=current_user.uid,
        session_id=session_id,
        external_workout_url=ext_url,
        healthkit_uuid=hk_uuid,
    )
    return success_response(SessionSchema.from_domain(session))


@router.post(
    "/{session_id}/abandon",
    status_code=status.HTTP_200_OK,
    response_model=SuccessEnvelope[SessionSchema],
    summary="Abandon a workout session",
    description="Explicitly abandon a workout session per SPEC §7.1 & §9.5.",
)
async def abandon_session(
    session_id: DocumentIdPath,
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[SessionSchema]:
    """POST /api/v1/sessions/{session_id}/abandon endpoint."""
    session = await service.abandon_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(SessionSchema.from_domain(session))


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=SuccessEnvelope[DiscardSessionResponse],
    summary="Discard a created session",
    description="Hard delete a pending session per Decision #6 & SPEC §9.5.",
)
async def discard_session(
    session_id: DocumentIdPath,
    current_user: AuthenticatedUser = Depends(get_authorized_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[DiscardSessionResponse]:
    """DELETE /api/v1/sessions/{session_id} discard endpoint."""
    res = await service.discard_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(DiscardSessionResponse.model_validate(res))
