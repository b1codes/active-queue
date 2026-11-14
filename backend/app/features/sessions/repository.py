from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from google.api_core.exceptions import Aborted, AlreadyExists, FailedPrecondition, NotFound
from google.cloud.firestore import ArrayUnion, async_transactional
from google.cloud.firestore_v1 import FieldFilter

from app.core.envelopes import ErrorDetail
from app.core.errors import ConflictError, NotFoundError
from app.features.sessions.models import Session

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient, AsyncTransaction

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
    except ValueError:  # bad base64, UTF-8, or ISO timestamp
        return None


# Claim attempts for the per-user active-session slot before reporting a conflict.
SLOT_CLAIM_ATTEMPTS = 4

# Transaction attempts for complete. Concurrent completes of one session (double taps)
# contend on the same documents; the SDK default of 5 can be exhausted by 4 contenders.
COMPLETE_TXN_ATTEMPTS = 10


def _active_session_conflict(active_session_id: str) -> ConflictError:
    return ConflictError(
        code="ACTIVE_SESSION_EXISTS",
        message="You already have an active session in progress",
        details=[ErrorDetail(field="active_session_id", issue=active_session_id)],
    )


class SessionRepository:
    """Firestore repository for sessions collection per SPEC §4.4, §7.1, §7.2, & §9.5."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def create_session(self, session: Session) -> Session:
        """Create a session, enforcing one non-terminal session per user atomically.

        The service's pre-check (get_active_user_session) is a query, so two concurrent
        POST /sessions could both pass it. To close that race, creation also claims
        active_session_slots/{user_id} with create() in the same batch as the session
        write: exactly one concurrent creator wins; the rest get AlreadyExists.

        A slot is never explicitly released. When a claim fails, the slot's session is
        re-read (which runs lazy abandonment); if it is terminal or gone, the slot is
        stale and is taken over with an update_time precondition so only one
        concurrent reclaimer can win.
        """
        slot_ref = self._client.collection("active_session_slots").document(session.user_id)
        session_ref = self._client.collection("sessions").document(session.id)
        slot = {"session_id": session.id, "updated_at": session.created_at}

        for _ in range(SLOT_CLAIM_ATTEMPTS):
            batch = self._client.batch()
            batch.create(slot_ref, slot)
            batch.set(session_ref, session.to_firestore())
            try:
                await batch.commit()
                break
            except (AlreadyExists, Aborted):
                pass

            slot_snap = await slot_ref.get()
            if not slot_snap.exists:
                continue  # released between our claim and read; claim again
            holder_id = str((slot_snap.to_dict() or {}).get("session_id", ""))
            holder = await self.get_session(holder_id) if holder_id else None
            if holder is not None and holder.status in ("pending", "in_progress"):
                raise _active_session_conflict(holder.id)

            batch = self._client.batch()
            batch.update(
                slot_ref,
                slot,
                option=self._client.write_option(last_update_time=slot_snap.update_time),
            )
            batch.set(session_ref, session.to_firestore())
            try:
                await batch.commit()
                break
            except (FailedPrecondition, Aborted, NotFound):
                continue  # another creator reclaimed first; re-evaluate
        else:
            slot_snap = await slot_ref.get()
            raise _active_session_conflict(str((slot_snap.to_dict() or {}).get("session_id", "")))

        logger.info("session_created", session_id=session.id, user_id=session.user_id)
        return session

    async def get_session(
        self, session_id: str, user_id: str | None = None, now: datetime | None = None
    ) -> Session | None:
        """Fetch a session document by ID with multi-user user_id validation and lazy abandonment check per SPEC §7.2."""
        if now is None:
            now = datetime.now(UTC)

        doc_ref = self._client.collection("sessions").document(session_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        session = Session.from_firestore(data)

        if user_id is not None and session.user_id != user_id:
            return None

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
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("status", "in", ["pending", "in_progress"]))
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
            filter=FieldFilter("user_id", "==", user_id)
        )

        if status_filter:
            query = query.where(filter=FieldFilter("status", "==", status_filter))

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
        """Atomically complete session, mark feed_item consumed, and arrayUnion content_id to user per SPEC §9.6.

        Runs as a single Firestore transaction so the status check and all three writes
        see one consistent snapshot: a concurrent double-tap cannot apply effects twice,
        and partial application (completed session, content still queued) is impossible.

        - The feed item is only updated if it exists: content-first sessions may target
          cached content that is not in this user's feed (update() on a missing doc
          would fail the whole transaction).
        - The user's consumed record is written with set(merge=True) so it lands even
          if users/{uid} has not been provisioned yet.
        """
        session_ref = self._client.collection("sessions").document(session_id)

        @async_transactional
        async def _complete(txn: AsyncTransaction) -> Session:
            session_snap = await session_ref.get(transaction=txn)
            if not session_snap.exists:
                raise NotFoundError(
                    code="SESSION_NOT_FOUND",
                    message=f"Session '{session_id}' not found",
                )

            session = Session.from_firestore(session_snap.to_dict() or {})

            if session.user_id != user_id:
                raise NotFoundError(
                    code="SESSION_NOT_FOUND",
                    message=f"Session '{session_id}' not found",
                )

            if session.status == "completed":
                # Idempotent: completing an already completed session returns 200 unchanged
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

            feed_item_ref = None
            if session.content_id:
                feed_item_ref = self._client.collection("feed_items").document(
                    f"{user_id}_{session.content_id}"
                )
                feed_snap = await feed_item_ref.get(transaction=txn)
                if not feed_snap.exists:
                    feed_item_ref = None

            # All reads above, all writes below (Firestore transaction rule).
            txn.update(
                session_ref,
                {"status": "completed", "completed_at": now, "updated_at": now},
            )
            if feed_item_ref is not None:
                txn.update(feed_item_ref, {"consumed": True, "updated_at": now})
            if session.content_id:
                txn.set(
                    self._client.collection("users").document(user_id),
                    {
                        "consumed_content_ids": ArrayUnion([session.content_id]),
                        "updated_at": now,
                    },
                    merge=True,
                )

            session.status = "completed"
            session.completed_at = now
            session.updated_at = now
            logger.info(
                "session_completed_transactionally", session_id=session_id, user_id=user_id
            )
            return session

        try:
            return await _complete(self._client.transaction(max_attempts=COMPLETE_TXN_ATTEMPTS))
        except Aborted:
            # Every attempt lost to a concurrent transaction on the same documents. For a
            # double-tap (SPEC §7.1) the winner was another complete of this session, so the
            # idempotent answer is the session as it now stands, not a 500.
            snap = await session_ref.get()
            current = Session.from_firestore(snap.to_dict() or {}) if snap.exists else None
            if (
                current is not None
                and current.user_id == user_id
                and current.status == "completed"
            ):
                logger.info("session_complete_contention_resolved", session_id=session_id)
                return current
            raise

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
