from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from google.cloud.firestore import ArrayUnion

from app.features.users.cache import auth_cache
from app.features.users.models import User, UserAuthorization

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

logger = structlog.get_logger(__name__)


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

        Per SPEC §3.2, first-login provisioning MUST create both documents in a single
        atomic batch/transaction. Updates in-process auth cache.
        """
        batch = self._client.batch()

        user_ref = self._client.collection("users").document(user.uid)
        auth_ref = self._client.collection("user_authorization").document(auth.uid)

        batch.set(user_ref, user.to_firestore())
        batch.set(auth_ref, auth.to_firestore())

        await batch.commit()

        # Update in-process cache
        auth_cache.set(auth.uid, auth)

        logger.info(
            "user_provisioned_transactional",
            uid=user.uid,
            email=user.email,
        )
        return user, auth

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

    async def mark_consumed(self, uid: str, content_id: str) -> None:
        """Atomically append content_id to user's consumed_content_ids array per SPEC §4.2.

        Wrapped in this abstraction so the eventual subcollection migration touches only this file.
        """
        doc_ref = self._client.collection("users").document(uid)
        await doc_ref.update({"consumed_content_ids": ArrayUnion([content_id])})
        logger.info("content_marked_consumed", uid=uid, content_id=content_id)
