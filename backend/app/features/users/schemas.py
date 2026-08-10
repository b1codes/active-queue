from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.users.models import User, UserAuthorization, UserPreferences


class UserAuthorizationSchema(BaseModel):
    """API schema for UserAuthorization response."""

    uid: str
    role: str
    status: str
    disabled: bool
    scopes: list[str]

    @classmethod
    def from_domain(cls, auth: UserAuthorization) -> UserAuthorizationSchema:
        return cls(
            uid=auth.uid,
            role=auth.role,
            status=auth.status,
            disabled=auth.disabled,
            scopes=auth.scopes,
        )


class UserSchema(BaseModel):
    """API schema for User response."""

    uid: str
    email: str
    display_name: str
    photo_url: str | None = None
    created_at: datetime
    updated_at: datetime
    preferences: UserPreferences

    @classmethod
    def from_domain(cls, user: User) -> UserSchema:
        return cls(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
            preferences=user.preferences,
        )


class UserMeData(BaseModel):
    """Payload for GET /api/v1/users/me endpoint."""

    user: UserSchema
    authorization: UserAuthorizationSchema


class UpdatePreferencesRequest(BaseModel):
    """Request schema for PATCH /api/v1/users/me/preferences per SPEC §4.2."""

    preferred_activity_types: list[str] | None = None
    preferred_tracker_app: str | None = None
    default_time_block_seconds: int | None = Field(None, ge=300, le=86400)
    hide_completed: bool | None = None
    dark_mode: bool | None = None
    sync_enabled: bool | None = None
    notifications_enabled: bool | None = None
