from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.core.envelopes import ErrorDetail
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.features.activities.service import ActivityService
from app.features.sessions.models import MatchMode, Session
from app.features.sessions.repository import SessionRepository

if TYPE_CHECKING:
    from app.features.content.repository import ContentRepository

logger = structlog.get_logger(__name__)

# Predefined time block allowlist in seconds per SPEC §5.3
VALID_TIME_BLOCK_DURATIONS = {900, 1200, 1800, 2700, 3600, 4500, 5400}


class SessionService:
    """Business logic for workout time-boxing sessions per SPEC §4.4, §7.1, & §9.5.

    Enforces business rules:
    - Content duration is READ FROM content_cache, NEVER from request body.
    - Bare time-first duration validated against predefined 7-block allowlist.
    - Single active session guardrail (ACTIVE_SESSION_EXISTS, 409).
    - Idempotent session start preserving original started_at timestamp.
    - Cross-user session access returns 404 (SESSION_NOT_FOUND), never 403.
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        activity_service: ActivityService | None = None,
        content_repo: ContentRepository | None = None,
    ) -> None:
        self._session_repo = session_repo
        self._activity_service = activity_service or ActivityService()
        self._content_repo = content_repo

    async def create_session(
        self,
        user_id: str,
        activity_id: str,
        match_mode: MatchMode,
        content_id: str | None = None,
        target_duration_seconds: int | None = None,
    ) -> Session:
        """Create a new workout time-boxing session per SPEC §7.1 & §9.5."""
        # Step 1: Validate activity existence
        activity = self._activity_service.get_activity(activity_id)

        # Step 2: Single active session guardrail
        existing_active = await self._session_repo.get_active_user_session(user_id)
        if existing_active:
            raise ConflictError(
                code="ACTIVE_SESSION_EXISTS",
                message="You already have an active session in progress",
                details=[
                    ErrorDetail(
                        field="active_session_id",
                        issue=existing_active.id,
                    )
                ],
            )

        # Step 3: Determine session duration
        duration_seconds: int = 0
        if content_id:
            if not self._content_repo:
                raise NotFoundError(
                    code="CONTENT_NOT_FOUND",
                    message=f"Content '{content_id}' not found",
                )
            cache_doc = await self._content_repo.get_content_cache(content_id)
            if not cache_doc:
                raise NotFoundError(
                    code="CONTENT_NOT_FOUND",
                    message=f"Content item '{content_id}' not found in cache",
                )
            # CRITICAL SECURITY RULE: duration is read from content_cache, never request body
            duration_seconds = cache_doc.duration_seconds
        else:
            # Bare time-first session: validate against 7-block allowlist
            if (
                target_duration_seconds is None
                or target_duration_seconds not in VALID_TIME_BLOCK_DURATIONS
            ):
                raise ValidationError(
                    code="DURATION_OUT_OF_RANGE",
                    message="Target duration must be one of the predefined time block options (15m, 20m, 30m, 45m, 60m, 75m, 90m)",
                )
            duration_seconds = target_duration_seconds

        # Step 4: Validate activity min/max duration bounds
        self._activity_service.validate_duration(activity.id, duration_seconds)

        # Step 5: Construct and persist pending session
        session_id = f"s_{uuid.uuid4().hex[:16]}"
        now = datetime.now(UTC)

        session = Session(
            id=session_id,
            user_id=user_id,
            activity_id=activity.id,
            match_mode=match_mode,
            content_id=content_id,
            duration_seconds=duration_seconds,
            status="pending",
            checklist_completed=False,
            started_at=None,
            completed_at=None,
            abandoned_at=None,
            created_at=now,
            updated_at=now,
        )

        saved = await self._session_repo.create_session(session)
        logger.info(
            "session_created_successfully",
            session_id=saved.id,
            user_id=user_id,
            duration_seconds=duration_seconds,
        )
        return saved

    async def start_session(self, user_id: str, session_id: str) -> Session:
        """Start a pending workout session per SPEC §7.1 & §9.5."""
        session = await self._session_repo.get_session(session_id)

        # Cross-user access returns 404, not 403 per SPEC & task instructions
        if not session or session.user_id != user_id:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        if session.status in ("completed", "abandoned"):
            raise ConflictError(
                code="SESSION_ALREADY_TERMINAL",
                message=f"Session '{session_id}' is terminal ({session.status}) and cannot be started",
            )

        # Idempotent re-fire: if already in_progress, return as-is
        if session.status == "in_progress":
            logger.info("session_start_idempotent", session_id=session_id, user_id=user_id)
            return session

        now = datetime.now(UTC)
        updates = {
            "status": "in_progress",
            "started_at": now,
            "checklist_completed": True,
            "updated_at": now,
        }

        await self._session_repo.update_session(session.id, updates)

        session.status = "in_progress"
        session.started_at = now
        session.checklist_completed = True
        session.updated_at = now

        logger.info("session_started", session_id=session_id, user_id=user_id)
        return session
