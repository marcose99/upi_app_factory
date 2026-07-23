from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response


def build_documentation_router(*, project_root: Path) -> APIRouter:
    router = APIRouter()
    root = project_root.resolve()
    html_path = root / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.html"
    manifest_path = root / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json"

    def _relative(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    def _documentation_payload() -> dict[str, Any]:
        if not html_path.is_file():
            raise HTTPException(status_code=404, detail={"status": "missing"})
        html = html_path.read_text(encoding="utf-8")
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                manifest = value
        return {
            "status": "available",
            "title": "UPI App Factory Complete Guide",
            "route": "/operator-portal/api/documentation/factory",
            "download_route": "/operator-portal/api/documentation/factory/download",
            "html_path": _relative(html_path),
            "manifest_path": _relative(manifest_path),
            "size_bytes": len(html.encode("utf-8")),
            "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "manifest": manifest,
            "operator_message": "Factory documentation is available as a local governed HTML download.",
        }

    @router.get("/operator-portal/api/documentation/factory")
    async def factory_documentation() -> dict[str, Any]:
        return _documentation_payload()

    @router.get("/operator-portal/api/documentation/factory/download")
    async def factory_documentation_download() -> Response:
        if not html_path.is_file():
            raise HTTPException(status_code=404, detail={"status": "missing"})
        return Response(
            content=html_path.read_text(encoding="utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": 'attachment; filename="UPI_APP_FACTORY_COMPLETE_GUIDE.html"'},
        )

    return router
