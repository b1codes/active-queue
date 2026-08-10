from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import get_db
from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.users.repository import UserRepository
from app.features.users.schemas import (
    UpdatePreferencesRequest,
    UserAuthorizationSchema,
    UserMeData,
    UserSchema,
)
from app.features.users.service import UserService

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(db: AsyncClient = Depends(get_db)) -> UserService:
    """FastAPI dependency injecting UserService."""
    return UserService(UserRepository(db))


@router.get("/me", response_model=None)
async def get_current_user_profile(
    auth_user: AuthenticatedUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """GET /api/v1/users/me — Fetch current authenticated user profile & authorization.

    Ensures first-login user provisioning and validates account authorization status per SPEC §4.2.
    """
    user, auth_doc = await service.ensure_user_provisioned(auth_user)
    data = UserMeData(
        user=UserSchema.from_domain(user),
        authorization=UserAuthorizationSchema.from_domain(auth_doc),
    )
    return success_response(data.model_dump())


@router.patch("/me/preferences", response_model=None)
async def update_current_user_preferences(
    body: UpdatePreferencesRequest,
    auth_user: AuthenticatedUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """PATCH /api/v1/users/me/preferences — Update user preferences per SPEC §4.2."""
    await service.ensure_user_provisioned(auth_user)
    updated_user = await service.update_user_preferences(auth_user.uid, body)
    return success_response(UserSchema.from_domain(updated_user).model_dump())
