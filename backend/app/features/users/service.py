from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.errors import AuthorizationError, NotFoundError
from app.features.users.models import User, UserAuthorization

if TYPE_CHECKING:
    from app.core.security import AuthenticatedUser
    from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


class UserService:
    """Business logic for user provisioning, authorization checks, and profiles.

    Holds NO HTTP types and NEVER touches Firestore client directly (uses UserRepository).
    """

    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    async def ensure_user_provisioned(
        self, auth_user: AuthenticatedUser
    ) -> tuple[User, UserAuthorization]:
        """Ensures user and user_authorization documents exist and checks authorization status.

        - If user_authorization document has status == "disabled" or disabled == True,
          raises AuthorizationError(code="ACCOUNT_DISABLED", message="Account disabled").
        - If first login (documents missing), provisions both documents atomically.
        """
        auth_doc = await self._repo.get_authorization(auth_user.uid)
        user_doc = await self._repo.get_user(auth_user.uid)

        if auth_doc is not None and (auth_doc.disabled or auth_doc.status == "disabled"):
            logger.warning(
                "account_disabled_access_attempt",
                uid=auth_user.uid,
            )
            raise AuthorizationError(
                code="ACCOUNT_DISABLED",
                message="Account disabled",
            )

        if user_doc is None or auth_doc is None:
            display_name = auth_user.name or (
                auth_user.email.split("@")[0] if auth_user.email else auth_user.uid
            )

            new_user = User(
                uid=auth_user.uid,
                email=auth_user.email or "",
                display_name=display_name,
                photo_url=auth_user.picture,
            )
            new_auth = UserAuthorization(
                uid=auth_user.uid,
                role="user",
                status="active",
                disabled=False,
            )

            user_doc, auth_doc = await self._repo.provision_user_transactional(new_user, new_auth)

        return user_doc, auth_doc

    async def get_user_profile(self, uid: str) -> User:
        """Fetch user profile by UID."""
        user = await self._repo.get_user(uid)
        if user is None:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User {uid} not found",
            )
        return user
