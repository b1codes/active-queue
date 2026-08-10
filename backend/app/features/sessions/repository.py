from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.features.sessions.models import Session

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

logger = structlog.get_logger(__name__)


class SessionRepository:
    """Firestore repository for sessions collection per SPEC §4.4 & §7.1."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def create_session(self, session: Session) -> Session:
        """Create a session document in sessions collection."""
        doc_ref = self._client.collection("sessions").document(session.id)
        await doc_ref.set(session.to_firestore())
        logger.info("session_created", session_id=session.id, user_id=session.user_id)
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Fetch a session document by ID."""
        doc_ref = self._client.collection("sessions").document(session_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return Session.from_firestore(data)

    async def get_active_user_session(self, user_id: str) -> Session | None:
        """Fetch active non-terminal session ('pending' or 'in_progress') for user_id."""
        query = (
            self._client.collection("sessions")
            .where(field_path="user_id", op_string="==", value=user_id)
            .where(field_path="status", op_string="in", value=["pending", "in_progress"])
            .limit(1)
        )
        snapshots = await query.get()
        if not snapshots:
            return None
        return Session.from_firestore(snapshots[0].to_dict() or {})

    async def update_session(self, session_id: str, updates: dict[str, Any]) -> None:
        """Update fields on a session document."""
        doc_ref = self._client.collection("sessions").document(session_id)
        await doc_ref.update(updates)
        logger.info("session_updated", session_id=session_id, fields=list(updates.keys()))
