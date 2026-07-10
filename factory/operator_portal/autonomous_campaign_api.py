from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from factory.operator_portal.autonomous_campaign import (
    AutonomousCampaignPortalError,
    AutonomousCampaignService,
)


class CampaignActionRequest(BaseModel):
    dry_run: bool = True
    approved: bool = False


def build_router(
    *,
    project_root: Path,
    campaign_config: Path,
) -> APIRouter:
    service = AutonomousCampaignService(
        project_root=project_root,
        campaign_config=campaign_config,
    )
    router = APIRouter(prefix="/api/autonomous-campaign")

    @router.get("/status")
    def status() -> dict[str, Any]:
        return service.status()

    @router.get("/events")
    def events(limit: int = 100) -> list[dict[str, Any]]:
        try:
            return service.events(limit=limit)
        except AutonomousCampaignPortalError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    @router.post("/{action}")
    def execute(
        action: str,
        request: CampaignActionRequest,
    ) -> dict[str, Any]:
        try:
            return service.execute(
                action,
                dry_run=request.dry_run,
                approved=request.approved,
            )
        except AutonomousCampaignPortalError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    return router
