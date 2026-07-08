from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.evidence_dashboard import build_dashboard_summary
from factory.operator_portal.validation_runner import CommandNotAllowedError, ValidationRunnerService


APP_ID = "upi_dispute_resolution"
PHASE = "phase35_operator_portal_local_web_api"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCAL_API_SAFETY_BOUNDARIES: dict[str, Any] = {
    "local_only": True,
    "certification_boundary": "certification_ready_not_certified",
    "official_certification_claimed": False,
    "official_certification_granted": False,
    "production_readiness_claimed": False,
    "local_readiness_scope": "local_operator_portal_api_only",
    "live_provider_calls_allowed": False,
    "real_secrets_allowed": False,
    "deployment_allowed": False,
    "merge_allowed": False,
    "tag_allowed": False,
    "push_allowed": False,
    "external_ecosystem_integrations": "mocked_or_simulated_only",
    "arbitrary_shell_text_allowed": False,
}


class ValidationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_ids: list[str] | None = None
    collect_all: bool = False
    dry_run: bool = False
    write_report: bool = True


class OperatorPortalLocalWebAPI:
    """Local FastAPI facade over governed operator portal services."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        download_center: DownloadCenterService | None = None,
        validation_runner: ValidationRunnerService | None = None,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.download_center = download_center or DownloadCenterService()
        self.validation_runner = validation_runner or ValidationRunnerService(
            project_root=self.project_root,
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "app_id": APP_ID,
            "phase": PHASE,
            "service": "operator_portal_local_web_api",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def evidence_dashboard(self) -> dict[str, Any]:
        payload = build_dashboard_summary(project_root=self.project_root)
        return {
            "status": "available",
            "payload": payload,
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def download_center_status(self) -> dict[str, Any]:
        dashboard = build_dashboard_summary(project_root=self.project_root)
        return {
            "status": "available",
            "download_center": dashboard.get("phase32_download_center_service_status", {}),
            "phase31_export_bundle_metadata": dashboard.get(
                "phase31_export_bundle_metadata",
                {},
            ),
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def export_download_bundle(self) -> dict[str, Any]:
        result = self.download_center.trigger_governed_export()
        return {
            "status": result.get("status", "unknown"),
            "export": result,
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def validation_runner_dry_run(self) -> dict[str, Any]:
        report = self.validation_runner.run(dry_run=True, write_report=False)
        return {
            "status": "dry_run",
            "report": report,
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def run_validation(self, request: ValidationRunRequest) -> dict[str, Any]:
        command_ids = tuple(request.command_ids) if request.command_ids is not None else None
        try:
            report = self.validation_runner.run(
                command_ids=command_ids,
                dry_run=request.dry_run,
                collect_all=request.collect_all,
                write_report=request.write_report,
            )
        except CommandNotAllowedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": report.get("status", "unknown"),
            "report": report,
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def latest_validation_report(self) -> dict[str, Any]:
        report_path = self.validation_runner.report_path
        if not report_path.is_absolute():
            report_path = self.project_root / report_path

        if not report_path.is_file():
            return {
                "status": "missing",
                "report_path": self._relative_path(report_path),
                "report": None,
                "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
            }

        value = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise HTTPException(status_code=500, detail="Latest validation report is not an object")
        return {
            "status": "available",
            "report_path": self._relative_path(report_path),
            "report": cast(dict[str, Any], value),
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def _relative_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return str(path)


def create_app(
    *,
    project_root: Path | None = None,
    download_center: DownloadCenterService | None = None,
    validation_runner: ValidationRunnerService | None = None,
) -> FastAPI:
    api = OperatorPortalLocalWebAPI(
        project_root=project_root,
        download_center=download_center,
        validation_runner=validation_runner,
    )
    app = FastAPI(
        title="Operator Portal Local Web API",
        version="phase35",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return api.health()

    @app.get("/portal/evidence-dashboard")
    async def evidence_dashboard() -> dict[str, Any]:
        return api.evidence_dashboard()

    @app.get("/portal/download-center/status")
    async def download_center_status() -> dict[str, Any]:
        return api.download_center_status()

    @app.post("/portal/download-center/export")
    async def export_download_bundle() -> dict[str, Any]:
        return api.export_download_bundle()

    @app.get("/portal/validation-runner/dry-run")
    async def validation_runner_dry_run() -> dict[str, Any]:
        return api.validation_runner_dry_run()

    @app.post("/portal/validation-runner/run")
    async def run_validation(request: ValidationRunRequest) -> dict[str, Any]:
        return api.run_validation(request)

    @app.get("/portal/validation-runner/latest-report")
    async def latest_validation_report() -> dict[str, Any]:
        return api.latest_validation_report()

    return app


app = create_app()
