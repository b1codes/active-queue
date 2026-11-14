from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from app.core.dependencies import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.features.users.repository import UserRepository
from app.features.users.service import UserService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient


async def get_authorized_user(
    auth_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
) -> AuthenticatedUser:
    """Authorization resolution run on every authenticated request per SPEC §3.2.

    Token verification alone is not enough: a verified token for an account whose
    user_authorization doc is disabled must get 403 ACCOUNT_DISABLED on every route,
    not just /users/me. First-login provisioning also happens here so that every
    downstream write (session completion, hide) can rely on users/{uid} existing.
    """
    await UserService(UserRepository(db)).ensure_authorized(auth_user)
    return auth_user
