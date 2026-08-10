from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from app.core.envelopes import SuccessEnvelope, success_response
from app.core.security import AuthenticatedUser, get_current_user
from app.features.activities.schemas import (
    ActivityListResponse,
    ActivitySchema,
    TimeBlockListResponse,
    TimeBlockSchema,
)
from app.features.activities.service import ActivityService

router = APIRouter(prefix="/activities", tags=["activities"])


def get_activity_service() -> ActivityService:
    """Dependency injector for ActivityService."""
    return ActivityService()


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="List predefined activities",
    description="Fetch static catalog of 9 predefined physical activities per SPEC §5.1 & §9.5.",
)
async def list_activities(
    _user: AuthenticatedUser = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """GET /api/v1/activities endpoint."""
    activities = service.list_activities()
    response_data = ActivityListResponse(
        activities=[ActivitySchema.from_domain(act) for act in activities]
    )
    return success_response(response_data.model_dump())


@router.get(
    "/time-blocks",
    status_code=status.HTTP_200_OK,
    response_model=None,
    summary="List predefined time blocks",
    description="Fetch static catalog of 7 predefined time blocks per SPEC §5.3 & §9.5.",
)
async def list_time_blocks(
    _user: AuthenticatedUser = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
) -> SuccessEnvelope[dict[str, Any]]:
    """GET /api/v1/activities/time-blocks endpoint."""
    time_blocks = service.list_time_blocks()
    response_data = TimeBlockListResponse(
        time_blocks=[TimeBlockSchema.from_domain(tb) for tb in time_blocks]
    )
    return success_response(response_data.model_dump())
