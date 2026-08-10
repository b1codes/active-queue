from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.activities.service import ActivityService
from app.features.content.repository import ContentRepository
from app.features.sessions.repository import SessionRepository
from app.features.sessions.schemas import CreateSessionRequest, SessionSchema
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
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SessionService = Depends(get_session_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """POST /api/v1/sessions/{session_id}/start endpoint."""
    session = await service.start_session(
        user_id=current_user.uid,
        session_id=session_id,
    )
    return success_response(SessionSchema.from_domain(session).model_dump())
