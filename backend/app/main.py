from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.core.config import settings
from app.core.firestore import close_firestore, init_firestore
from app.core.logging import configure_logging
from app.core.security import init_firebase_admin
from app.features.health.router import router as health_router
from app.features.users.router import router as users_router
from app.middleware.errors import (
    ErrorHandlingMiddleware,
    http_exception_handler,
    validation_error_handler,
)
from app.middleware.logging import RequestLoggingMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup and shutdown lifecycle for the FastAPI application."""
    configure_logging(debug=settings.debug, log_level=settings.log_level)
    await init_firestore(settings)
    init_firebase_admin(settings)
    yield
    await close_firestore()


app = FastAPI(
    title="ActiveQueue API",
    version="0.1.0",
    lifespan=lifespan,
)

# Exception Handlers
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]

# Middleware (outermost first — logging wraps error handling)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Health check at root (unauthenticated, no /api/v1 prefix)
app.include_router(health_router)

# Feature routers under /api/v1
app.include_router(users_router, prefix="/api/v1")
# app.include_router(content_router, prefix="/api/v1")
# app.include_router(sessions_router, prefix="/api/v1")
# app.include_router(activities_router, prefix="/api/v1")
