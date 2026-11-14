from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog
from google.api_core.exceptions import Aborted, AlreadyExists
from google.cloud.firestore import ArrayUnion

from app.features.users.cache import auth_cache
from app.features.users.models import User, UserAuthorization

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient, AsyncDocumentReference

logger = structlog.get_logger(__name__)

# Bounded retries for losers of a concurrent first-login provisioning race.
PROVISION_RACE_ATTEMPTS = 5


class UserRepository:
    """Firestore repository for users and user_authorization collections per SPEC §3.2 & §4.4.

    Owns all query construction, Firestore transactional logic, and in-process TTL caching.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def get_user(self, uid: str) -> User | None:
        """Fetch user profile document from users/{uid}."""
        doc_ref = self._client.collection("users").document(uid)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return User.from_firestore(data)

    async def get_authorization(
        self, uid: str, use_cache: bool = True
    ) -> UserAuthorization | None:
        """Fetch user authorization document from user_authorization/{uid}.

        Uses in-process TTL cache (60s TTL, max 1000 entries) to prevent an extra
        Firestore read (~5-15 ms) on every request per SPEC §3.2.
        """
        if use_cache:
            cached_auth = auth_cache.get(uid)
            if cached_auth is not None:
                return cached_auth

        doc_ref = self._client.collection("user_authorization").document(uid)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        auth_doc = UserAuthorization.from_firestore(data)

        if use_cache:
            auth_cache.set(uid, auth_doc)

        return auth_doc

    async def provision_user_transactional(
        self, user: User, auth: UserAuthorization
    ) -> tuple[User, UserAuthorization]:
        """Atomically provision users/{uid} and user_authorization/{uid} documents.

        Per SPEC §3.2, first-login provisioning MUST create both documents atomically.
        Uses one batch of create() writes (precondition: document must not exist), so:

        - both documents land together or not at all;
        - nothing is ever overwritten, so an existing users/{uid} (and its
          consumed_content_ids) survives;
        - the app fires several requests in parallel on first launch. A read-write
          transaction exhausts its retries under that contention; here a loser gets
          AlreadyExists (or a retryable Aborted), creates whichever document is still
          missing, and reads back the stored state.
        """
        user_ref = self._client.collection("users").document(user.uid)
        auth_ref = self._client.collection("user_authorization").document(auth.uid)

        batch = self._client.batch()
        batch.create(user_ref, user.to_firestore())
        batch.create(auth_ref, auth.to_firestore())
        try:
            await batch.commit()
            stored_user, stored_auth = user, auth
        except (AlreadyExists, Aborted):
            stored_user, stored_auth = await self._converge_provisioning(
                user_ref, auth_ref, user, auth
            )

        auth_cache.set(stored_auth.uid, stored_auth)
        logger.info("user_provisioned_transactional", uid=stored_user.uid, email=stored_user.email)
        return stored_user, stored_auth

    async def _converge_provisioning(
        self,
        user_ref: AsyncDocumentReference,
        auth_ref: AsyncDocumentReference,
        user: User,
        auth: UserAuthorization,
        attempts: int = PROVISION_RACE_ATTEMPTS,
    ) -> tuple[User, UserAuthorization]:
        """Create whichever provisioning doc is missing, then return what is stored."""
        for attempt in range(attempts):
            for ref, data in ((user_ref, user.to_firestore()), (auth_ref, auth.to_firestore())):
                with contextlib.suppress(AlreadyExists, Aborted):
                    await ref.create(data)
            user_snap = await user_ref.get()
            auth_snap = await auth_ref.get()
            if user_snap.exists and auth_snap.exists:
                return (
                    User.from_firestore(user_snap.to_dict() or {}),
                    UserAuthorization.from_firestore(auth_snap.to_dict() or {}),
                )
            await asyncio.sleep(0.05 * (2**attempt))
        msg = f"user provisioning did not converge for uid={user.uid}"
        raise RuntimeError(msg)

    async def update_user(self, uid: str, updates: dict[str, Any]) -> User | None:
        """Update fields on users/{uid} document."""
        doc_ref = self._client.collection("users").document(uid)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None

        await doc_ref.update(updates)
        updated_snap = await doc_ref.get()
        data = updated_snap.to_dict() or {}
        return User.from_firestore(data)

    async def is_consumed(self, uid: str, content_id: str) -> bool:
        """Check if content_id is in user's consumed_content_ids list per SPEC §4.2.

        Wrapped in this abstraction so the eventual subcollection migration (at 5,000 entries)
        touches only this repository file.
        """
        user = await self.get_user(uid)
        if user is None:
            return False
        return content_id in user.consumed_content_ids

    async def get_consumed_content_ids(self, uid: str) -> set[str]:
        """Return the durable consumed-content record for uid per SPEC §4.2 & §4.7.

        Sync uses this to project feed_items.consumed, so re-syncing or re-adding a
        playlist never resurfaces content the user already finished or hid.
        """
        user = await self.get_user(uid)
        return set(user.consumed_content_ids) if user else set()

    async def mark_consumed(self, uid: str, content_id: str) -> None:
        """Atomically append content_id to user's consumed_content_ids array per SPEC §4.2.

        Wrapped in this abstraction so the eventual subcollection migration touches only this file.
        """
        doc_ref = self._client.collection("users").document(uid)
        await doc_ref.update({"consumed_content_ids": ArrayUnion([content_id])})
        logger.info("content_marked_consumed", uid=uid, content_id=content_id)
