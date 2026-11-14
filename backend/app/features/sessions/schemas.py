from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.dependencies import ActivityId, DocumentId
from app.core.envelopes import DurationSeconds, RequestSchema, ResponseSchema
from app.core.sanitizer import sanitize_identifier, sanitize_url
from app.features.sessions.models import Session


class CreateSessionRequest(RequestSchema):
    """Request payload for POST /sessions per SPEC §9.5."""

    activity_id: ActivityId = Field(
        ..., description="ID of catalog activity, e.g. running or strength"
    )
    match_mode: Literal["content_first", "time_first"] = Field(
        ..., description="Session match mode: content_first or time_first"
    )
    content_id: DocumentId | None = Field(
        None, description="Namespaced content ID if matched from content"
    )
    target_duration_seconds: DurationSeconds | None = Field(
        None, description="Target duration in seconds for bare time-first sessions"
    )


class CompleteSessionRequest(RequestSchema):
    """Request payload for POST /sessions/{id}/complete per SPEC §9.6."""

    external_workout_url: str | None = Field(
        None, max_length=2048, description="External workout URL (reserved for v1.1)"
    )
    healthkit_uuid: str | None = Field(
        None, max_length=100, description="Apple HealthKit UUID (reserved for v1.1)"
    )

    @field_validator("external_workout_url")
    @classmethod
    def sanitize_ext_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_url(v)

    @field_validator("healthkit_uuid")
    @classmethod
    def sanitize_hk_uuid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitize_identifier(v, max_length=100)


class SessionSchema(ResponseSchema):
    """API response schema for a session per SPEC §9.5 & §9.6."""

    id: str
    user_id: str
    activity_id: str
    match_mode: Literal["content_first", "time_first"]
    content_id: str | None = None
    duration_seconds: int
    status: Literal["pending", "in_progress", "completed", "abandoned"]
    checklist_completed: bool
    started_at: datetime | None = None
    completed_at: datetime | None = None
    abandoned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, session: Session) -> SessionSchema:
        """Convert Session domain model to SessionSchema response."""
        return cls(
            id=session.id,
            user_id=session.user_id,
            activity_id=session.activity_id,
            match_mode=session.match_mode,
            content_id=session.content_id,
            duration_seconds=session.duration_seconds,
            status=session.status,
            checklist_completed=session.checklist_completed,
            started_at=session.started_at,
            completed_at=session.completed_at,
            abandoned_at=session.abandoned_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class SessionListResponse(ResponseSchema):
    """Response payload for GET /sessions list per SPEC §9.5."""

    items: list[SessionSchema]
    next_cursor: str | None = None


class DiscardSessionResponse(ResponseSchema):
    """Response payload for DELETE /sessions/{id} per Decision #6."""

    session_id: str
    discarded: bool
