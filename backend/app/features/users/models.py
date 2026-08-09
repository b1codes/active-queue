from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """User preferences stored inside users/{uid}.preferences document field."""

    dark_mode: bool = True
    sync_enabled: bool = True
    notifications_enabled: bool = True


class User(BaseModel):
    """Domain model for users/{uid} Firestore document shape per SPEC §4.4."""

    uid: str
    email: str
    display_name: str
    photo_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    def to_firestore(self) -> dict[str, Any]:
        """Convert model to Firestore document dict."""
        return {
            "uid": self.uid,
            "email": self.email,
            "display_name": self.display_name,
            "photo_url": self.photo_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "preferences": self.preferences.model_dump(),
        }

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> User:
        """Construct model from Firestore document dict."""
        return cls(
            uid=data.get("uid", ""),
            email=data.get("email", ""),
            display_name=data.get("display_name", ""),
            photo_url=data.get("photo_url"),
            created_at=data.get("created_at") or datetime.now(UTC),
            updated_at=data.get("updated_at") or datetime.now(UTC),
            preferences=UserPreferences(**(data.get("preferences") or {})),
        )


class UserAuthorization(BaseModel):
    """Domain model for user_authorization/{uid} Firestore document shape per SPEC §4.4.

    Deliberately separated from users/{uid}: read on every API request and must not be
    coupled to profile or preference write churn.
    """

    uid: str
    role: str = "user"
    status: str = "active"  # "active" | "disabled" | "pending"
    disabled: bool = False
    scopes: list[str] = Field(default_factory=lambda: ["read", "write"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_firestore(self) -> dict[str, Any]:
        """Convert model to Firestore document dict."""
        return {
            "uid": self.uid,
            "role": self.role,
            "status": self.status,
            "disabled": self.disabled,
            "scopes": self.scopes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> UserAuthorization:
        """Construct model from Firestore document dict."""
        return cls(
            uid=data.get("uid", ""),
            role=data.get("role", "user"),
            status=data.get("status", "active"),
            disabled=bool(data.get("disabled", False)),
            scopes=data.get("scopes") or ["read", "write"],
            created_at=data.get("created_at") or datetime.now(UTC),
            updated_at=data.get("updated_at") or datetime.now(UTC),
        )
