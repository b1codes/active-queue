from __future__ import annotations

from fastapi.security import HTTPBearer

# This is a stub for M0; real Firebase Auth token verification comes in M1
security = HTTPBearer()


async def verify_id_token() -> None:
    """
    Placeholder for token verification logic.
    """
    pass
