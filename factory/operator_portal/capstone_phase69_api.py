from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Response

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from upi_factory.capstone.phase69 import (  # noqa: E402
    CAMPAIGN_ID,
    Phase69Error,
    build_phase69_status,
    read_safe_evidence,
    read_safe_source,
    render_phase69_view,
    repository_root,
    run_phase69_demonstration,
)
from tools.factory_control_plane.common import default_state_root  # noqa: E402


def build_phase69_router(
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> APIRouter:
    root = (project_root or repository_root()).resolve()
    state = (state_root or default_state_root()).resolve()
    router = APIRouter(prefix="/operator-portal/api/capstone/phase69", tags=["phase69-capstone"])

    @router.get("/status")
    async def status() -> dict[str, Any]:
        try:
            return cast(dict[str, Any], build_phase69_status(project_root=root, state_root=state))
        except Phase69Error as exc:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": str(exc)}) from exc

    @router.post("/demonstration")
    async def demonstration() -> dict[str, Any]:
        try:
            return cast(dict[str, Any], run_phase69_demonstration(project_root=root, state_root=state))
        except Phase69Error as exc:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": str(exc)}) from exc

    @router.get("/view", include_in_schema=False)
    async def view() -> Response:
        payload = build_phase69_status(project_root=root, state_root=state)
        return Response(content=render_phase69_view(payload), media_type="text/html")

    @router.get("/source")
    async def source(path: str) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], read_safe_source(root, path))
        except Phase69Error as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "error": str(exc)}) from exc

    @router.get("/evidence")
    async def evidence(path: str) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], read_safe_evidence(state, CAMPAIGN_ID, path))
        except Phase69Error as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "error": str(exc)}) from exc

    @router.get("/downloads/recipient")
    async def recipient_download() -> Response:
        payload = build_phase69_status(project_root=root, state_root=state)
        bundle = root / payload["recipient_download"]["download_path"]
        return Response(
            content=bundle.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="phase69_recipient_application.zip"'},
        )

    return router
