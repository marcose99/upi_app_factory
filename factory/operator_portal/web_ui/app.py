from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response

from factory.operator_portal.browser_intake_orchestration import BrowserIntakeOrchestrator
from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.validation_runner import ValidationRunnerService


APP_ID = "upi_dispute_resolution"
PHASE = "phase36_operator_portal_local_web_ui"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEB_UI_ASSET_DIR = Path(__file__).resolve().parent / "static"

WEB_UI_ENDPOINTS = [
    "GET /health",
    "GET /portal/evidence-dashboard",
    "GET /portal/download-center/status",
    "POST /portal/download-center/export",
    "GET /portal/validation-runner/dry-run",
    "POST /portal/validation-runner/run",
    "GET /portal/validation-runner/latest-report",
]

WEB_UI_SAFETY_BOUNDARIES: dict[str, Any] = {
    "local_only": True,
    "certification_boundary": "certification_ready_not_certified",
    "official_certification_claimed": False,
    "official_certification_granted": False,
    "production_readiness_claimed": False,
    "local_readiness_scope": "local_operator_portal_browser_ui_only",
    "live_provider_calls_allowed": False,
    "real_secrets_allowed": False,
    "deployment_allowed": False,
    "merge_allowed": False,
    "tag_allowed": False,
    "push_allowed": False,
    "external_ecosystem_integrations": "mocked_or_simulated_only",
    "external_cdn_dependencies_allowed": False,
}


def get_web_ui_manifest() -> dict[str, Any]:
    assets = []
    for path in sorted(WEB_UI_ASSET_DIR.iterdir()):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assets.append(
                {
                    "path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "sha256": digest,
                    "size_bytes": path.stat().st_size,
                }
            )
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "asset_directory": WEB_UI_ASSET_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "assets": assets,
        "api_endpoints_consumed": WEB_UI_ENDPOINTS,
        "safety_boundaries": WEB_UI_SAFETY_BOUNDARIES,
    }


def create_web_ui_app(
    *,
    project_root: Path | None = None,
    download_center: DownloadCenterService | None = None,
    validation_runner: ValidationRunnerService | None = None,
    browser_orchestrator: BrowserIntakeOrchestrator | None = None,
) -> FastAPI:
    app = create_app(
        project_root=project_root or PROJECT_ROOT,
        download_center=download_center,
        validation_runner=validation_runner,
        browser_orchestrator=browser_orchestrator,
    )

    @app.get("/", include_in_schema=False)
    async def redirect_to_operator_ui() -> RedirectResponse:
        return RedirectResponse(url="/operator-ui/")

    @app.get("/portal/web-ui/manifest")
    async def web_ui_manifest() -> dict[str, Any]:
        return get_web_ui_manifest()

    @app.get("/operator-ui/", include_in_schema=False)
    async def operator_ui_index() -> Response:
        return Response(
            content=(WEB_UI_ASSET_DIR / "index.html").read_text(encoding="utf-8"),
            media_type="text/html",
        )

    @app.get("/operator-ui/app.js", include_in_schema=False)
    async def operator_ui_script() -> Response:
        return Response(
            content=(WEB_UI_ASSET_DIR / "app.js").read_text(encoding="utf-8"),
            media_type="text/javascript",
        )

    @app.get("/operator-ui/styles.css", include_in_schema=False)
    async def operator_ui_styles() -> Response:
        return Response(
            content=(WEB_UI_ASSET_DIR / "styles.css").read_text(encoding="utf-8"),
            media_type="text/css",
        )

    return app
