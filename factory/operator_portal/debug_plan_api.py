from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response

from factory.debugging import build_factory_debug_plan


def build_debug_plan_router(*, project_root: Path) -> APIRouter:
    router = APIRouter()
    root = project_root.resolve()

    @router.get("/operator-portal/api/debug-plan/factory")
    async def factory_debug_plan() -> dict[str, Any]:
        return build_factory_debug_plan(root)

    @router.get("/operator-portal/api/debug-plan/factory/download")
    async def factory_debug_plan_download() -> Response:
        payload = json.dumps(build_factory_debug_plan(root), indent=2, sort_keys=True) + "\n"
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="factory_debug_plan.json"'},
        )

    return router
