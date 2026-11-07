from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import firebase_admin
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from pydantic import BaseModel

from app.core.cache import TTLCache
from app.core.config import Settings, settings
from app.core.errors import AuthenticationError, AuthorizationError

logger = structlog.get_logger(__name__)

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AccountStatus:
    """The two Firebase Auth user-record fields that can invalidate a well-signed token."""

    disabled: bool
    tokens_valid_after_ms: int


# Revocation and Firebase-side disabling take effect within this TTL on a warm instance,
# the same staleness window SPEC §3.2 accepts for user_authorization deactivation.
account_status_cache: TTLCache[AccountStatus] = TTLCache(
    ttl_seconds=settings.auth_cache_ttl_seconds
)


async def fetch_account_status(uid: str) -> AccountStatus:
    """Read the Firebase Auth user record (one Identity Toolkit call, off the event loop)."""
    record = await asyncio.to_thread(auth.get_user, uid)
    return AccountStatus(
        disabled=bool(record.disabled),
        tokens_valid_after_ms=int(record.tokens_valid_after_timestamp or 0),
    )


async def enforce_account_status(uid: str, decoded_token: dict[str, Any]) -> None:
    """Reject tokens for deleted or disabled Firebase users and tokens issued before a revoke.

    This is what verify_id_token(check_revoked=True) does, but that variant calls
    Identity Toolkit on every request. Caching the user record per uid keeps it to one
    call per uid per TTL. A transient Identity Toolkit failure fails open: the token's
    signature, audience, issuer and expiry are already verified, and blocking every
    cache-missing user on an Auth outage would turn it into a full API outage.
    """
    status = account_status_cache.get(uid)
    if status is None:
        try:
            status = await fetch_account_status(uid)
        except auth.UserNotFoundError as exc:
            raise AuthenticationError(
                code="AUTH_TOKEN_INVALID",
                message="Auth token is invalid",
            ) from exc
        except (FirebaseError, ValueError):
            logger.warning("account_status_unavailable", uid=uid, exc_info=True)
            return
        account_status_cache.set(uid, status)

    if status.disabled:
        logger.warning("firebase_disabled_access_attempt", uid=uid)
        raise AuthorizationError(code="ACCOUNT_DISABLED", message="Account disabled")

    # google-auth rejects tokens without a numeric iat before we get here; treating a
    # missing one as 0 means it can only ever pass for a never-revoked account.
    issued_at = decoded_token.get("iat")
    if not isinstance(issued_at, int | float):
        issued_at = 0
    if issued_at * 1000 < status.tokens_valid_after_ms:
        raise AuthenticationError(
            code="AUTH_TOKEN_INVALID",
            message="Auth token has been revoked",
        )


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
    - AUTH_TOKEN_INVALID: Token signature or format is invalid, the token was revoked,
      or the Firebase user no longer exists.
    - ACCOUNT_DISABLED (403): the Firebase user record is disabled.

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

    await enforce_account_status(uid, decoded_token)

    # Bind uid to request state for structlog contextvar correlation
    request.state.uid = uid

    return AuthenticatedUser(
        uid=uid,
        email=decoded_token.get("email"),
        name=decoded_token.get("name"),
        picture=decoded_token.get("picture"),
        email_verified=bool(decoded_token.get("email_verified", False)),
    )
