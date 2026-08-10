from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

SessionStatus = Literal["pending", "in_progress", "completed", "abandoned"]
MatchMode = Literal["content_first", "time_first"]


@dataclass
class Session:
    """Domain model for a time-boxing workout session per SPEC §4.4 & §7.1."""

    id: str
    user_id: str
    activity_id: str
    match_mode: MatchMode
    content_id: str | None
    duration_seconds: int
    status: SessionStatus
    checklist_completed: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    abandoned_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_firestore(self) -> dict[str, Any]:
        """Convert domain model to Firestore dict."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "activity_id": self.activity_id,
            "match_mode": self.match_mode,
            "content_id": self.content_id,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "checklist_completed": self.checklist_completed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "abandoned_at": self.abandoned_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> Session:
        """Construct Session domain model from Firestore dict."""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            activity_id=data["activity_id"],
            match_mode=data["match_mode"],
            content_id=data.get("content_id"),
            duration_seconds=data["duration_seconds"],
            status=data["status"],
            checklist_completed=data.get("checklist_completed", False),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            abandoned_at=data.get("abandoned_at"),
            created_at=data.get("created_at", datetime.now(UTC)),
            updated_at=data.get("updated_at", datetime.now(UTC)),
        )
