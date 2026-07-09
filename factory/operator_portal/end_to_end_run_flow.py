from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.evidence_dashboard import build_dashboard_summary
from factory.operator_portal.validation_runner import ValidationRunnerService


APP_ID = "upi_dispute_resolution"
PHASE = "phase37_end_to_end_portal_run_flow"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase37"
)
DEFAULT_REPORT_PATH = ARTIFACT_DIR / "end_to_end_portal_run_flow_report.json"

REQUIREMENT_INTAKE_PATHS = (
    Path("factory_governance/phase2/upi_dispute_requirements.v1.json"),
    Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10/requirements_analysis.json"),
)
GENERATION_CONFIGURATION = {
    "generator_path": "factory/generators/mock_dispute_app_generator.py",
    "policy_path": "policies/phase30_deep_generated_application_regeneration_policy.json",
    "portal_command_id": "phase30_deep_generated_application_regeneration",
    "execution_mode": "not_executed_by_phase37_portal_flow",
}

SAFETY_BOUNDARIES = {
    "certification_boundary": "certification_ready_not_certified",
    "official_certification_claimed": False,
    "official_certification_granted": False,
    "production_readiness_claimed": False,
    "local_readiness_scope": "local_end_to_end_operator_portal_run_flow_only",
    "live_provider_calls_allowed": False,
    "real_secrets_allowed": False,
    "deployment_allowed": False,
    "merge_allowed": False,
    "tag_allowed": False,
    "push_allowed": False,
    "external_ecosystem_integrations": "mocked_or_simulated_only",
    "destructive_workspace_replacement_allowed": False,
    "generation_success_claimed": False,
}


class EndToEndPortalRunFlowService:
    """Governed local orchestration over existing operator portal services."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        download_center: DownloadCenterService | None = None,
        validation_runner: ValidationRunnerService | None = None,
        report_path: Path | None = None,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.download_center = download_center or DownloadCenterService()
        self.validation_runner = validation_runner or ValidationRunnerService()
        self.report_path = report_path or DEFAULT_REPORT_PATH

    def run(
        self,
        *,
        validation_command_ids: tuple[str, ...] = ("phase34_runner_self_check",),
        collect_all: bool = True,
        write_report: bool = True,
    ) -> dict[str, Any]:
        stages: dict[str, dict[str, Any]] = {}
        stages["intake_requirements_available"] = self._intake_requirements_stage()
        stages["generation_command"] = self._generation_command_stage()

        export_result: dict[str, Any] | None = None
        try:
            export_result = self.download_center.trigger_governed_export()
            stages["export_bundle_ready"] = {
                "status": "passed",
                "state": "ready",
                "bundle_path": export_result.get("bundle_path"),
                "export_manifest_path": export_result.get("export_manifest_path"),
            }
            stages["download_available"] = {
                "status": "passed",
                "state": "available",
                "download_ready_path": export_result.get("download_ready_path"),
            }
        except Exception as exc:
            stages["export_bundle_ready"] = {
                "status": "failed",
                "state": "failed",
                "reason": str(exc),
            }
            stages["download_available"] = {
                "status": "missing",
                "state": "missing",
                "reason": "export_bundle_not_ready",
            }

        dry_run_report = self.validation_runner.run(
            command_ids=validation_command_ids,
            dry_run=True,
            collect_all=collect_all,
            write_report=False,
        )
        stages["validation_dry_run_ready"] = {
            "status": "passed" if dry_run_report.get("dry_run") is True else "failed",
            "state": "ready" if dry_run_report.get("dry_run") is True else "failed",
            "command_ids": [
                entry.get("command_id")
                for entry in dry_run_report.get("command_results", [])
                if isinstance(entry, dict)
            ],
        }

        run_report = self.validation_runner.run(
            command_ids=validation_command_ids,
            dry_run=False,
            collect_all=collect_all,
            write_report=True,
        )
        run_status = run_report.get("status")
        stages["validation_run"] = {
            "status": "passed" if run_status == "passed" else "failed",
            "state": "passed" if run_status == "passed" else "failed",
            "runner_status": run_status,
            "report_path": run_report.get("report_path"),
            "command_results": run_report.get("command_results", []),
        }

        dashboard_summary = build_dashboard_summary(project_root=self.project_root)
        dashboard_status = cast(
            dict[str, Any],
            dashboard_summary.get("phase34_validation_runner_report_status", {}),
        )
        stages["evidence_dashboard_updated"] = {
            "status": (
                "passed"
                if dashboard_status.get("run_report_status") == "available"
                else "missing"
            ),
            "state": (
                "updated"
                if dashboard_status.get("run_report_status") == "available"
                else "missing"
            ),
            "dashboard_phase": dashboard_summary.get("phase"),
            "validation_report_status": dashboard_status.get("run_report_status"),
        }

        report = {
            "app_id": APP_ID,
            "phase": PHASE,
            "status": self._overall_status(stages),
            "stages": stages,
            "generation_status": {
                "success_claimed": False,
                "generation_executed_by_phase37": False,
                "reason": "Phase 37 only reports configured/unavailable generation command state.",
            },
            "export_result": self._summarize_export_result(export_result),
            "validation_dry_run_report": dry_run_report,
            "validation_run_report": run_report,
            "evidence_dashboard_summary": dashboard_summary,
            "safety_boundaries": SAFETY_BOUNDARIES,
        }
        if write_report:
            self._write_report(report)
        return report

    def _intake_requirements_stage(self) -> dict[str, Any]:
        files = []
        for path in REQUIREMENT_INTAKE_PATHS:
            exists = (self.project_root / path).is_file()
            files.append({"path": path.as_posix(), "exists": exists})
        available = any(item["exists"] for item in files)
        return {
            "status": "available" if available else "missing",
            "state": "available" if available else "missing",
            "files": files,
        }

    def _generation_command_stage(self) -> dict[str, Any]:
        generator_path = self.project_root / GENERATION_CONFIGURATION["generator_path"]
        policy_path = self.project_root / GENERATION_CONFIGURATION["policy_path"]
        configured = generator_path.is_file() and policy_path.is_file()
        return {
            "status": "configured" if configured else "unavailable",
            "state": "configured" if configured else "unavailable",
            **GENERATION_CONFIGURATION,
            "generator_exists": generator_path.is_file(),
            "policy_exists": policy_path.is_file(),
            "success_claimed": False,
            "executed": False,
            "execution_status": "skipped",
            "skip_reason": "Phase 37 does not execute generation or claim generation success.",
        }

    def _summarize_export_result(self, export_result: dict[str, Any] | None) -> dict[str, Any]:
        if export_result is None:
            return {"status": "missing", "download_available": False}
        return {
            "status": export_result.get("status"),
            "phase31_export_invoked": export_result.get("phase31_export_invoked"),
            "bundle_metadata": export_result.get("bundle_metadata", {}),
            "bundle_path": export_result.get("bundle_path"),
            "download_ready_path": export_result.get("download_ready_path"),
        }

    def _overall_status(self, stages: dict[str, dict[str, Any]]) -> str:
        if any(stage.get("status") == "failed" for stage in stages.values()):
            return "failed"
        if any(stage.get("status") in {"missing", "unavailable"} for stage in stages.values()):
            return "skipped"
        return "passed"

    def _write_report(self, report: dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def run_end_to_end_portal_flow(
    *,
    validation_command_ids: tuple[str, ...] = ("phase34_runner_self_check",),
    collect_all: bool = True,
    write_report: bool = True,
) -> dict[str, Any]:
    return EndToEndPortalRunFlowService().run(
        validation_command_ids=validation_command_ids,
        collect_all=collect_all,
        write_report=write_report,
    )
