from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from google.cloud.firestore import ArrayUnion

from app.core.errors import ConflictError, NotFoundError
from app.features.sessions.models import Session

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

logger = structlog.get_logger(__name__)

# 24 hours in seconds per SPEC §7.2
ABANDONMENT_GRACE_PERIOD_SECONDS = 86400


def encode_session_cursor(dt: datetime) -> str:
    """Encode datetime cursor for session pagination."""
    return base64.urlsafe_b64encode(dt.isoformat().encode("utf-8")).decode("utf-8")


def decode_session_cursor(cursor_str: str) -> datetime | None:
    """Decode session datetime cursor."""
    try:
        raw_str = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        return datetime.fromisoformat(raw_str)
    except Exception:
        return None


class SessionRepository:
    """Firestore repository for sessions collection per SPEC §4.4, §7.1, §7.2, & §9.5."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def create_session(self, session: Session) -> Session:
        """Create a session document in sessions collection."""
        doc_ref = self._client.collection("sessions").document(session.id)
        await doc_ref.set(session.to_firestore())
        logger.info("session_created", session_id=session.id, user_id=session.user_id)
        return session

    async def get_session(self, session_id: str, now: datetime | None = None) -> Session | None:
        """Fetch a session document by ID with lazy abandonment check per SPEC §7.2."""
        if now is None:
            now = datetime.now(UTC)

        doc_ref = self._client.collection("sessions").document(session_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        session = Session.from_firestore(data)

        # Lazy abandonment evaluation per SPEC §7.2
        if session.status in ("pending", "in_progress"):
            cutoff = session.created_at + timedelta(
                seconds=session.duration_seconds + ABANDONMENT_GRACE_PERIOD_SECONDS
            )
            if now > cutoff:
                logger.info(
                    "lazy_abandonment_triggered",
                    session_id=session.id,
                    user_id=session.user_id,
                )
                await doc_ref.update(
                    {
                        "status": "abandoned",
                        "abandoned_at": now,
                        "updated_at": now,
                    }
                )
                session.status = "abandoned"
                session.abandoned_at = now
                session.updated_at = now

        return session

    async def get_active_user_session(
        self, user_id: str, now: datetime | None = None
    ) -> Session | None:
        """Fetch active non-terminal session ('pending' or 'in_progress') for user_id with lazy abandonment evaluation per SPEC §7.2."""
        if now is None:
            now = datetime.now(UTC)

        query = (
            self._client.collection("sessions")
            .where(field_path="user_id", op_string="==", value=user_id)
            .where(field_path="status", op_string="in", value=["pending", "in_progress"])
            .limit(1)
        )
        snapshots = await query.get()
        if not snapshots:
            return None

        data = snapshots[0].to_dict() or {}
        session = Session.from_firestore(data)

        # Lazy abandonment evaluation: now > created_at + duration_seconds + 24h per SPEC §7.2
        cutoff = session.created_at + timedelta(
            seconds=session.duration_seconds + ABANDONMENT_GRACE_PERIOD_SECONDS
        )
        if now > cutoff:
            logger.info(
                "lazy_abandonment_swept_active_session",
                session_id=session.id,
                user_id=user_id,
            )
            doc_ref = self._client.collection("sessions").document(session.id)
            await doc_ref.update(
                {
                    "status": "abandoned",
                    "abandoned_at": now,
                    "updated_at": now,
                }
            )
            session.status = "abandoned"
            session.abandoned_at = now
            session.updated_at = now
            return None  # Session is now abandoned, so no active session exists

        return session

    async def get_user_sessions_page(
        self,
        user_id: str,
        limit: int = 20,
        cursor_dt: datetime | None = None,
        status_filter: str | None = None,
    ) -> tuple[list[Session], str | None]:
        """Fetch paginated session history for user_id per SPEC §9.5."""
        query = self._client.collection("sessions").where(
            field_path="user_id", op_string="==", value=user_id
        )

        if status_filter:
            query = query.where(field_path="status", op_string="==", value=status_filter)

        query = query.order_by("created_at", direction="DESCENDING")

        if cursor_dt is not None:
            query = query.start_after({"created_at": cursor_dt})

        query = query.limit(limit + 1)
        snapshots = await query.get()

        results: list[Session] = []
        for snap in snapshots[:limit]:
            data = snap.to_dict() or {}
            results.append(Session.from_firestore(data))

        next_cursor: str | None = None
        if len(snapshots) > limit and results:
            last_item = results[-1]
            next_cursor = encode_session_cursor(last_item.created_at)

        return results, next_cursor

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

    async def abandon_session(self, session_id: str, user_id: str, now: datetime) -> Session:
        """Explicitly mark session as abandoned per SPEC §7.1 & §9.5."""
        doc_ref = self._client.collection("sessions").document(session_id)
        snapshot = await doc_ref.get()

        if not snapshot.exists:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        data = snapshot.to_dict() or {}
        session = Session.from_firestore(data)

        if session.user_id != user_id:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        if session.status == "abandoned":
            # Idempotent: abandoning an already abandoned session returns 200 with unchanged session
            logger.info("session_abandon_idempotent", session_id=session_id, user_id=user_id)
            return session

        if session.status == "completed":
            raise ConflictError(
                code="SESSION_ALREADY_TERMINAL",
                message="Completed session cannot be abandoned",
            )

        updates = {
            "status": "abandoned",
            "abandoned_at": now,
            "updated_at": now,
        }
        await doc_ref.update(updates)

        session.status = "abandoned"
        session.abandoned_at = now
        session.updated_at = now

        logger.info("session_explicitly_abandoned", session_id=session_id, user_id=user_id)
        return session

    async def discard_session(self, session_id: str, user_id: str) -> None:
        """Hard delete a pending session from Firestore collection per Decision #6 & SPEC §9.5."""
        doc_ref = self._client.collection("sessions").document(session_id)
        snapshot = await doc_ref.get()

        if not snapshot.exists:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        data = snapshot.to_dict() or {}
        session = Session.from_firestore(data)

        if session.user_id != user_id:
            raise NotFoundError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
            )

        if session.status == "in_progress":
            raise ConflictError(
                code="SESSION_ALREADY_STARTED",
                message="Cannot discard a session that is already in progress. Use abandon instead.",
            )

        if session.status in ("completed", "abandoned"):
            raise ConflictError(
                code="SESSION_ALREADY_TERMINAL",
                message=f"Cannot discard a terminal ({session.status}) session.",
            )

        # Hard delete per decision #6
        await doc_ref.delete()
        logger.info("session_hard_deleted_discard", session_id=session_id, user_id=user_id)
