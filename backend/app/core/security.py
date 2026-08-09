from __future__ import annotations

import os

import firebase_admin
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from pydantic import BaseModel

from app.core.config import Settings, settings
from app.core.errors import AuthenticationError

security = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Authenticated user context populated from verified Firebase ID token."""

    uid: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    email_verified: bool = False


def init_firebase_admin(app_settings: Settings = settings) -> None:
    """Initialize Firebase Admin SDK with emulator configuration if needed."""
    if app_settings.firebase_auth_emulator_host:
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = app_settings.firebase_auth_emulator_host

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": app_settings.gcp_project_id})


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthenticatedUser:
    """FastAPI dependency that verifies the Firebase ID token from the Authorization header.

    Distinguishes specific token errors per SPEC §3.1:
    - AUTH_TOKEN_MISSING: No Bearer token provided in Authorization header.
    - AUTH_TOKEN_EXPIRED: Token expired (client uses this to trigger one-shot refresh retry).
    - AUTH_TOKEN_INVALID: Token signature or format is invalid.

    On successful verification, binds uid to request.state.uid for structlog correlation.
    """
    if not credentials or not credentials.credentials:
        raise AuthenticationError(
            code="AUTH_TOKEN_MISSING",
            message="Authorization header missing or invalid format",
        )

    token = credentials.credentials

    # Ensure Firebase Admin SDK is initialized
    init_firebase_admin(settings)

    try:
        decoded_token = auth.verify_id_token(token, check_revoked=False)
    except auth.ExpiredIdTokenError as exc:
        raise AuthenticationError(
            code="AUTH_TOKEN_EXPIRED",
            message="Auth token has expired",
        ) from exc
    except (
        auth.InvalidIdTokenError,
        auth.RevokedIdTokenError,
        auth.CertificateFetchError,
        FirebaseError,
    ) as exc:
        raise AuthenticationError(
            code="AUTH_TOKEN_INVALID",
            message="Auth token is invalid",
        ) from exc
    except Exception as exc:
        raise AuthenticationError(
            code="AUTH_TOKEN_INVALID",
            message="Failed to verify auth token",
        ) from exc

    uid = str(decoded_token.get("uid", ""))
    if not uid:
        raise AuthenticationError(
            code="AUTH_TOKEN_INVALID",
            message="Auth token does not contain a valid uid",
        )

    # Bind uid to request state for structlog contextvar correlation
    request.state.uid = uid

    return AuthenticatedUser(
        uid=uid,
        email=decoded_token.get("email"),
        name=decoded_token.get("name"),
        picture=decoded_token.get("picture"),
        email_verified=bool(decoded_token.get("email_verified", False)),
    )
