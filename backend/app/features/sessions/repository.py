from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from google.cloud.firestore import ArrayUnion

from app.core.errors import ConflictError, NotFoundError
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

    async def complete_session_transaction(
        self,
        session_id: str,
        user_id: str,
        now: datetime,
    ) -> Session:
        """Atomically complete session, mark feed_item consumed, and arrayUnion content_id to user per SPEC §9.6."""
        session_ref = self._client.collection("sessions").document(session_id)
        session_snap = await session_ref.get()

        if not session_snap.exists:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        data = session_snap.to_dict() or {}
        session = Session.from_firestore(data)

        if session.user_id != user_id:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        if session.status == "completed":
            # Idempotent: completing an already completed session returns 200 with unchanged session
            logger.info("session_complete_idempotent", session_id=session_id, user_id=user_id)
            return session

        if session.status == "pending":
            raise ConflictError(
                code="SESSION_NOT_STARTED",
                message="Session has not been started yet and cannot be completed",
            )

        if session.status == "abandoned":
            raise ConflictError(
                code="SESSION_ALREADY_TERMINAL",
                message="Session is abandoned and cannot be completed",
            )

        session_updates = {
            "status": "completed",
            "completed_at": now,
            "updated_at": now,
        }

        feed_item_ref = None
        user_ref = None
        if session.content_id:
            feed_doc_id = f"{user_id}_{session.content_id}"
            feed_item_ref = self._client.collection("feed_items").document(feed_doc_id)
            user_ref = self._client.collection("users").document(user_id)

        # Single atomic batch write to prevent partial state application per SPEC §9.6
        batch = self._client.batch()
        batch.update(session_ref, session_updates)
        if feed_item_ref:
            batch.update(feed_item_ref, {"consumed": True, "updated_at": now})
        if user_ref and session.content_id:
            batch.update(
                user_ref,
                {"consumed_content": ArrayUnion([session.content_id]), "updated_at": now},
            )

        await batch.commit()

        session.status = "completed"
        session.completed_at = now
        session.updated_at = now

        logger.info("session_completed_transactionally", session_id=session_id, user_id=user_id)
        return session
