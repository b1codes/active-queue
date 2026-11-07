"""Mocked integration tier: real routing/middleware, Firestore and token verification mocked.

Authorization resolution (user_authorization lookup, first-login provisioning, 403 on
disabled accounts) needs real Firestore semantics, so it is exercised in tests/emulator.
Here it is reduced to token verification so each test only has to mock what it is about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.features.users.dependencies import get_authorized_user
from app.main import app

if TYPE_CHECKING:
    from collections.abc import Iterator


async def _token_verification_only(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    # Depending on get_current_user (rather than overriding with it directly) lets FastAPI
    # share one verification per request with enforce_user_rate_limit, as in production.
    return user


@pytest.fixture(autouse=True)
def _authorization_is_token_verification_only() -> Iterator[None]:
    app.dependency_overrides[get_authorized_user] = _token_verification_only
    yield
    app.dependency_overrides.pop(get_authorized_user, None)
