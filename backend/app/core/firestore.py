from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from google.cloud.firestore import AsyncClient

if TYPE_CHECKING:
    from app.core.config import Settings

logger = structlog.get_logger(__name__)

_client: AsyncClient | None = None


async def init_firestore(settings: Settings) -> None:
    """Initialize the Firestore AsyncClient with emulator wiring.

    The Firestore SDK reads FIRESTORE_EMULATOR_HOST from the environment
    to route requests to the emulator. We set it here from the Settings
    object so that no other module needs to read os.environ directly.
    """
    global _client

    if settings.firestore_emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
        logger.info(
            "firestore_emulator_configured",
            host=settings.firestore_emulator_host,
        )

    _client = AsyncClient(project=settings.gcp_project_id)
    logger.info("firestore_initialized", project=settings.gcp_project_id)


async def close_firestore() -> None:
    """Close the Firestore client and release resources."""
    global _client
    if _client is not None:
        _client.close()  # type: ignore[no-untyped-call]
        _client = None
        logger.info("firestore_closed")


def get_firestore_client() -> AsyncClient:
    """Return the initialized Firestore client.

    Raises RuntimeError if called before init_firestore().
    """
    if _client is None:
        msg = (
            "Firestore client not initialized. "
            "Ensure init_firestore() is called during application startup."
        )
        raise RuntimeError(msg)
    return _client
