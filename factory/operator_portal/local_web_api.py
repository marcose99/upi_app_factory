from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, cast

from fastapi import FastAPI, HTTPException, status
from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from starlette.middleware.base import RequestResponseEndpoint

from factory.observability import (
    configure_logging,
    get_logger,
    logging_context,
    trace_context_from_traceparent,
)
from factory.operator_portal.browser_intake_orchestration import (
    BrowserIntakeOrchestrator,
    OrchestrationConflict,
    OrchestrationNotFound,
    OrchestrationValidationError,
)
from factory.operator_portal.capstone_phase69_api import build_phase69_router
from factory.operator_portal.debug_plan_api import build_debug_plan_router
from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.documentation_api import build_documentation_router
from factory.operator_portal.deep_portal_integration import (
    DeepPortalError,
    DeepPortalIntegration,
)
from factory.operator_portal.evidence_dashboard import build_dashboard_summary
from factory.operator_portal.operator_guides import build_operator_guide_index
from factory.operator_portal.portfolio_api import build_portfolio_router
from factory.operator_portal.runtime_api import build_runtime_router
from factory.operator_portal.state_roots import resolve_state_roots
from factory.operator_portal.token_economics_dashboard import build_dashboard as build_token_economics_dashboard
from factory.operator_portal.validation_runner import CommandNotAllowedError, ValidationRunnerService
from factory.native_capability_prerun.improvement_workflow import (
    FactoryImprovementError,
    ImprovementWorkflowConfig,
    run_factory_improvement_workflow,
)


APP_ID = "upi_dispute_resolution"
PHASE = "phase35_operator_portal_local_web_api"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_REQUIREMENTS_PATH = Path("examples/requirements/01_upi_failed_debit_no_credit.md")
LOGGER = get_logger(__name__)

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
PRIMARY_RUNTIME_PLANE = "portfolio_authoritative"
COMPATIBILITY_RUNTIME_PLANE = "runtime_compatibility_deprecated"


class ValidationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_ids: list[str] | None = None
    collect_all: bool = False
    dry_run: bool = False
    write_report: bool = True


class RequirementsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: str
    app_id: str | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = "operator"
    approval_token: str


class DeepPortalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: str | None = None
    requirements_path: str | None = None
    approval_token: str | None = None


class FactoryImprovementProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    improvement_requirements_path: str
    improvement_sha256: str
    output_root: str | None = None
    requirements_document_path: str | None = None
    application_id: str | None = None


class OperatorPortalLocalWebAPI:
    """Local FastAPI facade over governed operator portal services."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        download_center: DownloadCenterService | None = None,
        validation_runner: ValidationRunnerService | None = None,
        browser_orchestrator: BrowserIntakeOrchestrator | None = None,
        browser_state_root: Path | None = None,
        publication_root: Path | None = None,
        portfolio_state_root: Path | None = None,
        runtime_state_root: Path | None = None,
        phase69_state_root: Path | None = None,
    ) -> None:
        roots = resolve_state_roots(
            project_root=project_root or PROJECT_ROOT,
            browser_state_root=browser_state_root,
            portfolio_state_root=portfolio_state_root,
        )
        self.project_root = roots.project_root
        self.browser_state_root = roots.browser_state_root
        self.portfolio_state_root = roots.portfolio_state_root
        self.runtime_state_root = runtime_state_root
        self.phase69_state_root = phase69_state_root
        self.download_center = download_center or DownloadCenterService()
        self.validation_runner = validation_runner or ValidationRunnerService(
            project_root=self.project_root,
        )
        self.browser_orchestrator = browser_orchestrator or BrowserIntakeOrchestrator(
            project_root=self.project_root,
            state_root=self.browser_state_root,
            publication_root=publication_root,
            portfolio_state_root=self.portfolio_state_root,
        )
        self.deep_portal = DeepPortalIntegration(project_root=self.project_root)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "app_id": APP_ID,
            "phase": PHASE,
            "service": "operator_portal_local_web_api",
            "state_roots": {
                "browser_runs": str(self.browser_orchestrator.state_root),
                "portfolio": str(self.browser_orchestrator.portfolio_store.state_root),
                "runtime": str(self.runtime_state_root) if self.runtime_state_root else "default",
                "phase69": str(self.phase69_state_root) if self.phase69_state_root else "default",
                "strategy": "explicit_portal_state_roots",
            },
            "runtime_plane_authority": self.runtime_plane_authority(),
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def runtime_plane_authority(self) -> dict[str, Any]:
        return {
            "primary_runtime_plane": PRIMARY_RUNTIME_PLANE,
            "compatibility_runtime_plane": {
                "id": COMPATIBILITY_RUNTIME_PLANE,
                "mounted_prefix": "/operator-portal/api/runtime",
                "status": "deprecated_compatibility_surface",
                "replacement_prefix": "/operator-portal/api/portfolio/runtime",
                "ui_primary_surface": "/operator-portal/api/portfolio/runtime",
            },
            "capability_publication_surface": "/operator-portal/api/portfolio/catalogue",
            "authoritative_application_id": "upi_failed_debit_no_credit",
            "compatibility_application_id": APP_ID,
        }

    def evidence_dashboard(self) -> dict[str, Any]:
        payload = build_dashboard_summary(project_root=self.project_root)
        return {
            "status": "available",
            "payload": payload,
            "operator_message": "Evidence dashboard loaded from local lifecycle artifacts.",
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
            "operator_message": "Download status is read from local export metadata.",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def token_economics_dashboard(self) -> dict[str, Any]:
        return {
            "status": "available",
            "payload": build_token_economics_dashboard(project_root=self.project_root),
            "operator_message": "Token-economics policy, rate-card, budget, and applicability summary loaded from local configuration.",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def export_download_bundle(self) -> dict[str, Any]:
        try:
            result = self.download_center.trigger_governed_export()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "operator_message": "The governed local export did not complete.",
                    "next_steps": [
                        "Run the Phase 32 download center validator.",
                        "Check workspace write permissions for local export artifacts.",
                        "Do not retry by using deployment, merge, tag, or push commands.",
                    ],
                    "error": str(exc),
                    "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
                },
            ) from exc
        return {
            "status": result.get("status", "unknown"),
            "export": result,
            "operator_message": "Governed local export completed through the download center.",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def validation_runner_dry_run(self) -> dict[str, Any]:
        report = self.validation_runner.run(dry_run=True, write_report=False)
        return {
            "status": "dry_run",
            "report": report,
            "operator_message": "Dry run listed approved validation commands without execution.",
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
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "rejected",
                    "operator_message": "Validation request rejected: use approved command IDs only.",
                    "next_steps": [
                        "Run the validation dry-run endpoint to list approved command IDs.",
                        "Use phase34_runner_self_check for the local portal self-check.",
                        "Do not paste arbitrary shell text into the portal API.",
                    ],
                    "error": str(exc),
                    "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
                },
            ) from exc
        return {
            "status": report.get("status", "unknown"),
            "report": report,
            "operator_message": "Validation run finished; inspect command_results for details.",
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
                "operator_message": "No latest validation report exists yet.",
                "next_steps": [
                    "Run a validation dry-run to confirm approved commands.",
                    "Run the safe self-check to create a local report.",
                ],
                "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
            }

        value = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "operator_message": "Latest validation report is malformed.",
                    "next_steps": [
                        "Re-run the safe validation self-check.",
                        "If the report remains malformed, inspect the local report path.",
                    ],
                    "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
                },
            )
        return {
            "status": "available",
            "report_path": self._relative_path(report_path),
            "report": cast(dict[str, Any], value),
            "operator_message": "Latest validation report loaded from local workspace.",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def operator_guides(self) -> dict[str, Any]:
        return {
            "status": "available",
            "payload": build_operator_guide_index(project_root=self.project_root),
            "operator_message": "Operator guides and status taxonomy are available locally.",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def sample_requirements(self) -> dict[str, Any]:
        sample_path = self.project_root / SAMPLE_REQUIREMENTS_PATH
        text = sample_path.read_text(encoding="utf-8")
        import hashlib

        return {
            "status": "available",
            "path": SAMPLE_REQUIREMENTS_PATH.as_posix(),
            "requirements": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "operator_message": (
                "Sample requirements loaded locally. Operators may still paste or upload "
                "their own requirements through the intake workflow."
            ),
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def validate_requirements(self, request: RequirementsRequest) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.validate_requirements(request.requirements)
        except OrchestrationValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "rejected",
                    "operator_message": "Requirements validation failed.",
                    "errors": exc.errors,
                    "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
                },
            ) from exc

    def create_browser_run(self, request: RequirementsRequest) -> dict[str, Any]:
        try:
            run = self.browser_orchestrator.create_run(
                request.requirements,
                app_id=request.app_id or APP_ID,
            )
        except OrchestrationValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "rejected",
                    "operator_message": "Run was not created because requirements validation failed.",
                    "errors": exc.errors,
                    "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
                },
            ) from exc
        return {
            "status": "run_created",
            "run_id": run["run_id"],
            "state": run["state"],
            "app_id": run["app_id"],
            "requirements_sha256": run["requirements_sha256"],
            "approval_required": run["approval_required"],
            "mock_boundary": run["mock_boundary"],
            "real_payment_calls": run["real_payment_calls"],
            "llm_calls": run["llm_calls"],
            "run": run,
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def browser_run(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.get_run(run_id)
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def plan_browser_run(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.plan(run_id)
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)})
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def approve_browser_run(self, run_id: str, request: ApprovalRequest) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.approve(
                run_id,
                actor=request.actor,
                approval_token=request.approval_token,
            )
        except OrchestrationValidationError as exc:
            raise HTTPException(status_code=403, detail={"status": "rejected", "errors": exc.errors})
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)})
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def execute_browser_run(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.execute(run_id)
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)})
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def cancel_browser_run(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.cancel(run_id)
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)})
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def browser_run_events(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.events(run_id)
        except OrchestrationNotFound:
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def browser_run_evidence(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.evidence(run_id)
        except OrchestrationNotFound:
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def browser_run_validation(self, run_id: str) -> dict[str, Any]:
        try:
            return self.browser_orchestrator.validation(run_id)
        except OrchestrationNotFound:
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})

    def native_pre_run_artifact(self, run_id: str, artifact: str) -> dict[str, Any]:
        if "/" in artifact or "\\" in artifact or artifact.startswith("."):
            raise HTTPException(status_code=400, detail={"status": "rejected", "error": "invalid artifact"})
        try:
            run = self.browser_orchestrator.get_run(run_id)
        except (OrchestrationNotFound, FileNotFoundError):
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id})
        plan = run.get("plan")
        pre_run = plan.get("native_capability_pre_run") if isinstance(plan, dict) else None
        artifact_root = pre_run.get("artifact_root") if isinstance(pre_run, dict) else None
        if not isinstance(artifact_root, str) or not artifact_root:
            raise HTTPException(status_code=404, detail={"status": "missing", "artifact": artifact})
        root = Path(artifact_root).expanduser().resolve()
        publication_root = self.browser_orchestrator.publication_root.resolve()
        if (
            not root.is_relative_to(self.project_root.resolve())
            and not root.is_relative_to(self.browser_state_root.resolve())
            and not root.is_relative_to(publication_root)
        ):
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": "untrusted artifact root"})
        path = (root / artifact).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=404, detail={"status": "missing", "artifact": artifact})
        data = path.read_bytes()
        import hashlib

        return {
            "schema_version": "native-pre-run-artifact-read.v1",
            "run_id": run_id,
            "artifact": artifact,
            "path": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "text": data.decode("utf-8") if len(data) <= 256 * 1024 else "",
            "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES,
        }

    def _resolve_trusted_local_path(self, value: str, *, label: str) -> Path:
        candidate = Path(value).expanduser()
        resolved = (candidate if candidate.is_absolute() else self.project_root / candidate).resolve()
        trusted_roots = (
            self.project_root.resolve(),
            self.browser_state_root.resolve(),
            self.browser_orchestrator.publication_root.resolve(),
        )
        if not any(resolved.is_relative_to(root) for root in trusted_roots):
            raise FactoryImprovementError(f"{label} must stay inside a trusted local root")
        return resolved

    def factory_improvement_proposal(self, request: FactoryImprovementProposalRequest) -> dict[str, Any]:
        try:
            improvement_path = self._resolve_trusted_local_path(
                request.improvement_requirements_path,
                label="improvement requirements path",
            )
            output_root = (
                self._resolve_trusted_local_path(request.output_root, label="factory improvement output root")
                if request.output_root
                else self.project_root / "workspace" / "factory_improvement_proposals"
            )
            trusted_output_root = (self.project_root / "workspace").resolve()
            if not output_root.is_relative_to(trusted_output_root):
                raise FactoryImprovementError("factory improvement output root must stay inside workspace")
            requirements_document = (
                self._resolve_trusted_local_path(
                    request.requirements_document_path,
                    label="requirements document path",
                )
                if request.requirements_document_path
                else None
            )
            result = run_factory_improvement_workflow(
                ImprovementWorkflowConfig(
                    improvement_requirements=improvement_path,
                    improvement_sha256=request.improvement_sha256,
                    output_root=output_root,
                    factory_root=self.project_root,
                    requirements_document=requirements_document,
                    application_id=request.application_id,
                    plan_only=True,
                )
            )
        except FactoryImprovementError as exc:
            raise HTTPException(status_code=400, detail={"status": "rejected", "error": str(exc)}) from exc
        return {"status": "proposal_ready", "result": result, "safety_boundaries": LOCAL_API_SAFETY_BOUNDARIES}

    def deep_overview(self) -> dict[str, Any]:
        try:
            return self.deep_portal.overview()
        except DeepPortalError as exc:
            raise HTTPException(status_code=500, detail={"status": "error", "error": str(exc)}) from exc

    def deep_compile(self, request: DeepPortalRequest) -> dict[str, Any]:
        try:
            return self.deep_portal.compile(request.model_dump(exclude_none=True))
        except DeepPortalError as exc:
            raise HTTPException(status_code=400, detail={"status": "rejected", "error": str(exc)}) from exc

    def deep_proposal(self, request: DeepPortalRequest) -> dict[str, Any]:
        try:
            return self.deep_portal.proposal(request.model_dump(exclude_none=True))
        except DeepPortalError as exc:
            raise HTTPException(status_code=400, detail={"status": "rejected", "error": str(exc)}) from exc

    def deep_approved_run(self, request: DeepPortalRequest) -> dict[str, Any]:
        try:
            return self.deep_portal.approved_run(request.model_dump(exclude_none=True))
        except DeepPortalError as exc:
            raise HTTPException(status_code=403, detail={"status": "rejected", "error": str(exc)}) from exc

    def deep_source_file(self, path: str) -> dict[str, Any]:
        try:
            return self.deep_portal.read_source(path)
        except (DeepPortalError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "error": str(exc)}) from exc

    def deep_evidence_file(self, path: str) -> dict[str, Any]:
        try:
            return self.deep_portal.read_evidence(path)
        except (DeepPortalError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "error": str(exc)}) from exc

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
    browser_orchestrator: BrowserIntakeOrchestrator | None = None,
    browser_state_root: Path | None = None,
    publication_root: Path | None = None,
    runtime_state_root: Path | None = None,
    portfolio_state_root: Path | None = None,
    phase69_state_root: Path | None = None,
) -> FastAPI:
    configure_logging(service_name="operator_portal_local_web_api", service_version="phase35")
    api = OperatorPortalLocalWebAPI(
        project_root=project_root,
        download_center=download_center,
        validation_runner=validation_runner,
        browser_orchestrator=browser_orchestrator,
        browser_state_root=browser_state_root,
        publication_root=publication_root,
        portfolio_state_root=portfolio_state_root,
        runtime_state_root=runtime_state_root,
        phase69_state_root=phase69_state_root,
    )
    app = FastAPI(
        title="Operator Portal Local Web API",
        version="phase35",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def structured_request_logging(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id")
        context = trace_context_from_traceparent(
            request.headers.get("traceparent"),
            request_id=request_id,
        )
        with logging_context(**context, correlation_id=context.get("request_id")):
            try:
                response = await call_next(request)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                LOGGER.exception(
                    "Request failed closed.",
                    extra={
                        "event_name": "http.request.failed",
                        "attributes": {
                            "http.request.method": request.method,
                            "url.path": request.url.path,
                            "http.response.status_code": 500,
                            "duration_ms": duration_ms,
                            "outcome": "failure",
                            "error.type": type(exc).__name__,
                            "error.message": "Internal server error.",
                        },
                    },
                )
                raise
            headers = {
                "traceparent": f"00-{context['trace_id']}-{context['span_id']}-{context['trace_flags']}",
                "x-request-id": context["request_id"],
            }
            if request.url.path.startswith("/operator-portal/api/runtime"):
                headers.update(
                    {
                        "deprecation": "true",
                        "x-upi-runtime-plane": COMPATIBILITY_RUNTIME_PLANE,
                        "x-upi-runtime-plane-primary": PRIMARY_RUNTIME_PLANE,
                        "link": '</operator-portal/api/runtime-plane-authority>; rel="successor-version"',
                    }
                )
            response.headers.update(headers)
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            LOGGER.info(
                "Request completed.",
                extra={
                    "event_name": "http.request.completed",
                    "attributes": {
                        "http.request.method": request.method,
                        "url.path": request.url.path,
                        "http.response.status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "outcome": "success" if response.status_code < 500 else "failure",
                    },
                },
            )
            return response

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return api.health()

    @app.get("/operator-portal/health")
    async def operator_portal_health() -> dict[str, Any]:
        return api.health()

    @app.get("/operator-portal/api/runtime-plane-authority")
    async def runtime_plane_authority() -> dict[str, Any]:
        return api.runtime_plane_authority()

    @app.get("/portal/evidence-dashboard")
    async def evidence_dashboard() -> dict[str, Any]:
        return api.evidence_dashboard()

    @app.get("/portal/download-center/status")
    async def download_center_status() -> dict[str, Any]:
        return api.download_center_status()

    @app.get("/portal/token-economics")
    async def token_economics_dashboard() -> dict[str, Any]:
        return api.token_economics_dashboard()

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

    @app.get("/portal/operator-guides")
    async def operator_guides() -> dict[str, Any]:
        return api.operator_guides()

    @app.get("/operator-portal/api/requirements/sample")
    async def sample_requirements() -> dict[str, Any]:
        return api.sample_requirements()

    @app.post("/operator-portal/api/requirements/validate")
    async def validate_requirements(request: RequirementsRequest) -> dict[str, Any]:
        return api.validate_requirements(request)

    @app.post("/operator-portal/api/runs", status_code=status.HTTP_201_CREATED)
    async def create_browser_run(request: RequirementsRequest) -> dict[str, Any]:
        return api.create_browser_run(request)

    @app.get("/operator-portal/api/runs/{run_id}")
    async def browser_run(run_id: str) -> dict[str, Any]:
        return api.browser_run(run_id)

    @app.post("/operator-portal/api/runs/{run_id}/plan")
    async def plan_browser_run(run_id: str) -> dict[str, Any]:
        return api.plan_browser_run(run_id)

    @app.post("/operator-portal/api/runs/{run_id}/approvals")
    async def approve_browser_run(run_id: str, request: ApprovalRequest) -> dict[str, Any]:
        return api.approve_browser_run(run_id, request)

    @app.post("/operator-portal/api/runs/{run_id}/execute", status_code=status.HTTP_202_ACCEPTED)
    async def execute_browser_run(run_id: str) -> dict[str, Any]:
        return api.execute_browser_run(run_id)

    @app.post("/operator-portal/api/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    async def cancel_browser_run(run_id: str) -> dict[str, Any]:
        return api.cancel_browser_run(run_id)

    @app.get("/operator-portal/api/runs/{run_id}/events")
    async def browser_run_events(run_id: str) -> dict[str, Any]:
        return api.browser_run_events(run_id)

    @app.get("/operator-portal/api/runs/{run_id}/evidence")
    async def browser_run_evidence(run_id: str) -> dict[str, Any]:
        return api.browser_run_evidence(run_id)

    @app.get("/operator-portal/api/runs/{run_id}/validation")
    async def browser_run_validation(run_id: str) -> dict[str, Any]:
        return api.browser_run_validation(run_id)

    @app.get("/operator-portal/api/runs/{run_id}/native-pre-run/artifacts/{artifact}")
    async def native_pre_run_artifact(run_id: str, artifact: str) -> dict[str, Any]:
        return api.native_pre_run_artifact(run_id, artifact)

    @app.post("/operator-portal/api/factory-improvement/proposal")
    async def factory_improvement_proposal(request: FactoryImprovementProposalRequest) -> dict[str, Any]:
        return api.factory_improvement_proposal(request)

    @app.get("/operator-portal/api/deep-engineering/overview")
    async def deep_engineering_overview() -> dict[str, Any]:
        return api.deep_overview()

    @app.post("/operator-portal/api/deep-engineering/compile")
    async def deep_engineering_compile(request: DeepPortalRequest) -> dict[str, Any]:
        return api.deep_compile(request)

    @app.post("/operator-portal/api/deep-engineering/proposal")
    async def deep_engineering_proposal(request: DeepPortalRequest) -> dict[str, Any]:
        return api.deep_proposal(request)

    @app.post("/operator-portal/api/deep-engineering/approved-run")
    async def deep_engineering_approved_run(request: DeepPortalRequest) -> dict[str, Any]:
        return api.deep_approved_run(request)

    @app.get("/operator-portal/api/deep-engineering/source")
    async def deep_engineering_source(path: str) -> dict[str, Any]:
        return api.deep_source_file(path)

    @app.get("/operator-portal/api/deep-engineering/evidence")
    async def deep_engineering_evidence(path: str) -> dict[str, Any]:
        return api.deep_evidence_file(path)

    @app.get("/operator-portal/api/deep-engineering/download/source")
    async def deep_engineering_source_archive() -> Response:
        archive = api.deep_portal.source_archive()
        return Response(
            content=archive.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="phase58_source.zip"'},
        )

    @app.get("/operator-portal/api/deep-engineering/download/evidence")
    async def deep_engineering_evidence_archive() -> Response:
        archive = api.deep_portal.evidence_archive()
        return Response(
            content=archive.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="phase58_evidence.zip"'},
        )

    @app.get("/operator-portal/api/runs/{run_id}/downloads/application")
    async def download_browser_application(run_id: str) -> Response:
        try:
            archive = api.browser_orchestrator.application_archive(run_id)
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)}) from exc
        except (OrchestrationNotFound, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id}) from exc
        return Response(
            content=archive.read_bytes(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{run_id}_generated_application.zip"'
                )
            },
        )

    @app.get("/operator-portal/api/runs/{run_id}/downloads/evidence")
    async def download_browser_evidence(run_id: str) -> Response:
        try:
            archive = api.browser_orchestrator.evidence_archive(run_id)
        except OrchestrationConflict as exc:
            raise HTTPException(status_code=409, detail={"status": "conflict", "error": str(exc)}) from exc
        except (OrchestrationNotFound, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail={"status": "missing", "run_id": run_id}) from exc
        return Response(
            content=archive.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}_evidence_bundle.zip"'},
        )

    runtime_router = build_runtime_router(project_root=api.project_root, state_root=runtime_state_root)
    portfolio_router = build_portfolio_router(project_root=api.project_root, state_root=api.portfolio_state_root)
    phase69_router = build_phase69_router(project_root=api.project_root, state_root=phase69_state_root)
    debug_plan_router = build_debug_plan_router(project_root=api.project_root)
    documentation_router = build_documentation_router(project_root=api.project_root)
    route_keys = {
        (
            getattr(route, "path", ""),
            tuple(sorted(getattr(route, "methods", set()) or set())),
        )
        for route in app.routes
    }
    for router in (runtime_router, portfolio_router, phase69_router, debug_plan_router, documentation_router):
        for route in router.routes:
            key = (
                getattr(route, "path", ""),
                tuple(sorted(getattr(route, "methods", set()) or set())),
            )
            if key not in route_keys:
                app.routes.append(route)
                route_keys.add(key)
    return app


app = create_app()
