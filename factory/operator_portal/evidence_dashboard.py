from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast


APP_ID = "upi_dispute_resolution"
PHASE = "phase33_operator_portal_run_validation_evidence_dashboard"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALIDATOR_COMMANDS = [
    "python scripts/validate_phase34_operator_portal_validation_runner.py",
    "python scripts/validate_phase33_operator_portal_evidence_dashboard.py",
    "python scripts/validate_phase32_operator_portal_download_center.py",
    "python scripts/validate_phase31_deep_generated_application_export_download_center.py",
    "python scripts/validate_phase30_deep_generated_application_regeneration.py",
    "python scripts/validate_phase29_generated_application_deep_structure_generator.py",
    "python scripts/validate_phase28_generated_application_architecture_depth_blueprint.py",
]

TEST_COMMANDS = [
    "python -m pytest tests/test_phase34_operator_portal_validation_runner.py",
    "python -m pytest tests/test_phase33_operator_portal_evidence_dashboard.py",
    "python -m pytest tests/test_phase32_operator_portal_download_center.py",
    "python -m pytest tests/test_phase31_deep_generated_application_export_download_center.py",
    "python -m pytest tests/test_phase30_deep_generated_application_regeneration.py",
    "python -m pytest tests/test_phase29_generated_application_deep_structure_generator.py",
    (
        "python -m pytest tests/test_phase11c_agentic_prompt_best_practices.py "
        "tests/test_phase11c_llm_call_metrics_prompt_policy.py "
        "tests/test_phase28_generated_application_architecture_depth_blueprint.py"
    ),
]

PHASE_ARTIFACTS = {
    "phase28": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/architecture_depth_artifact_manifest.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/certification_boundary.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/phase28_architecture_depth_audit.json",
    ],
    "phase29": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_audit.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_gate.json",
    ],
    "phase30": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/deep_generated_application_regeneration_audit.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/deep_generated_application_regeneration_gate.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/controlled_regeneration_output_manifest.json",
    ],
    "phase31": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase31/deep_generated_application_export_download_audit.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase31/deep_generated_application_export_download_gate.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase31/operator_download_center_manifest.json",
    ],
    "phase32": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_audit.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_gate.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_manifest.json",
    ],
    "phase34": [
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_runner_audit.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_runner_gate.json",
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_runner_manifest.json",
    ],
}

PHASE31_EXPORT_MANIFEST = (
    "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/"
    "staging/phase31_deep_generated_application_bundle/export_manifest.json"
)
PHASE31_GENERATION_MANIFEST = (
    "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/"
    "staging/phase31_deep_generated_application_bundle/generation_manifest.json"
)
PHASE31_ZIP = (
    "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/"
    "phase31_deep_generated_application_bundle.zip"
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def _git_values(project_root: Path, args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _artifact_status(project_root: Path, relative_paths: list[str]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    present_count = 0
    for relative_path in relative_paths:
        path = project_root / relative_path
        exists = path.is_file()
        if exists:
            present_count += 1
        entries.append(
            {
                "path": relative_path,
                "status": "available" if exists else "missing",
                "exists": exists,
            }
        )

    if present_count == len(relative_paths):
        status = "available"
    elif present_count == 0:
        status = "missing"
    else:
        status = "partial"
    return {"status": status, "files": entries}


class EvidenceDashboardService:
    """Read-only local evidence dashboard for governed operator inspection."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT

    def build_summary(self) -> dict[str, Any]:
        lifecycle_artifacts = {
            phase: _artifact_status(self.project_root, paths)
            for phase, paths in PHASE_ARTIFACTS.items()
        }
        export_metadata = self._phase31_export_bundle_metadata()
        return {
            "app_id": APP_ID,
            "phase": PHASE,
            "phase_coverage": {
                "current": "phase33",
                "covered_phases": [
                    "phase28",
                    "phase29",
                    "phase30",
                    "phase31",
                    "phase32",
                    "phase33",
                    "phase34",
                ],
                "posture": "certification_ready_not_certified",
            },
            "latest_relevant_tags": self._latest_relevant_tags(),
            "lifecycle_artifact_availability": lifecycle_artifacts,
            "phase31_export_bundle_metadata": export_metadata,
            "phase32_download_center_service_status": self._phase32_status(),
            "phase34_validation_runner_report_status": self._phase34_status(),
            "validator_commands": VALIDATOR_COMMANDS,
            "test_commands": TEST_COMMANDS,
            "safety_boundaries": {
                "certification_boundary": "certification_ready_not_certified",
                "official_certification_claimed": False,
                "official_certification_granted": False,
                "production_readiness_claimed": False,
                "live_provider_calls_allowed": False,
                "real_secrets_allowed": False,
                "deployment_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
                "mocked_simulated_ecosystem_boundary": True,
            },
            "dashboard_success_claim": self._dashboard_success_claim(
                lifecycle_artifacts,
                export_metadata,
            ),
        }

    def _latest_relevant_tags(self) -> dict[str, Any]:
        tags = _git_values(self.project_root, ["tag", "--list", "v0.*", "--sort=-creatordate"])
        relevant = [
            tag
            for tag in tags
            if any(version in tag for version in ["v0.28", "v0.29", "v0.30", "v0.31", "v0.32"])
        ][:8]
        return {
            "status": "available" if relevant else "unknown",
            "tags": relevant,
        }

    def _phase31_export_bundle_metadata(self) -> dict[str, Any]:
        export_manifest_path = self.project_root / PHASE31_EXPORT_MANIFEST
        generation_manifest_path = self.project_root / PHASE31_GENERATION_MANIFEST
        zip_path = self.project_root / PHASE31_ZIP
        export_manifest = _read_json(export_manifest_path)
        generation_manifest = _read_json(generation_manifest_path)

        if export_manifest is None:
            return {
                "status": "missing",
                "export_manifest_path": PHASE31_EXPORT_MANIFEST,
                "generation_manifest_path": PHASE31_GENERATION_MANIFEST,
                "zip_path": PHASE31_ZIP,
                "bundle_ready": False,
                "reason": "export_manifest_missing",
            }

        return {
            "status": "available" if zip_path.is_file() else "partial",
            "bundle_ready": zip_path.is_file() and generation_manifest is not None,
            "bundle_id": export_manifest.get("bundle_id", "unknown"),
            "app_id": export_manifest.get("app_id", "unknown"),
            "phase": export_manifest.get("phase", "unknown"),
            "zip_path": PHASE31_ZIP,
            "zip_status": "available" if zip_path.is_file() else "missing",
            "zip_size_bytes": zip_path.stat().st_size if zip_path.is_file() else None,
            "included_files_count": export_manifest.get("included_files_count", "unknown"),
            "evidence_files": export_manifest.get("evidence_files", []),
            "validation_commands": export_manifest.get("validation_commands", []),
            "generation_manifest_status": (
                "available" if generation_manifest is not None else "missing"
            ),
            "certification_boundary": export_manifest.get(
                "certification_boundary",
                "unknown",
            ),
            "official_certification_claimed": export_manifest.get(
                "official_certification_claimed",
                "unknown",
            ),
            "official_certification_granted": export_manifest.get(
                "official_certification_granted",
                "unknown",
            ),
            "production_readiness_claimed": export_manifest.get(
                "production_readiness_claimed",
                False,
            ),
            "live_provider_calls_allowed": export_manifest.get(
                "live_provider_calls_allowed",
                "unknown",
            ),
            "real_secrets_allowed": export_manifest.get("real_secrets_allowed", "unknown"),
            "deployment_allowed": export_manifest.get("deployment_allowed", "unknown"),
            "external_ecosystem_integrations": export_manifest.get(
                "external_ecosystem_integrations",
                "unknown",
            ),
        }

    def _phase32_status(self) -> dict[str, Any]:
        service_path = self.project_root / "factory/operator_portal/download_center.py"
        manifest_path = (
            self.project_root
            / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase32/operator_portal_download_center_manifest.json"
        )
        manifest = _read_json(manifest_path)
        return {
            "status": "available" if service_path.is_file() and manifest is not None else "missing",
            "service_path": "factory/operator_portal/download_center.py",
            "service_exists": service_path.is_file(),
            "manifest_status": "available" if manifest is not None else "missing",
            "phase31_export_entrypoint": (
                manifest.get("phase31_export_entrypoint", "unknown")
                if manifest is not None
                else "unknown"
            ),
            "validation_entrypoint": (
                manifest.get("validation_entrypoint", "unknown")
                if manifest is not None
                else "unknown"
            ),
        }

    def _phase34_status(self) -> dict[str, Any]:
        service_path = self.project_root / "factory/operator_portal/validation_runner.py"
        report_path = (
            self.project_root
            / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_run_report.json"
        )
        report = _read_json(report_path)
        return {
            "status": "available" if service_path.is_file() and report is not None else "missing",
            "service_path": "factory/operator_portal/validation_runner.py",
            "service_exists": service_path.is_file(),
            "run_report_path": (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_run_report.json"
            ),
            "run_report_status": "available" if report is not None else "missing",
            "run_status": report.get("status", "unknown") if report is not None else "unknown",
            "dry_run": report.get("dry_run", "unknown") if report is not None else "unknown",
            "command_count": (
                len(report.get("command_results", [])) if report is not None else 0
            ),
            "certification_boundary": (
                report.get("safety_boundaries", {}).get("certification_boundary", "unknown")
                if report is not None
                else "unknown"
            ),
        }

    def _dashboard_success_claim(
        self,
        lifecycle_artifacts: dict[str, dict[str, Any]],
        export_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        missing_phases = [
            phase
            for phase, status in lifecycle_artifacts.items()
            if status.get("status") != "available"
        ]
        if missing_phases or export_metadata.get("status") != "available":
            return {
                "status": "not_claimed",
                "reason": "missing_or_partial_evidence",
                "missing_or_partial_phases": missing_phases,
            }
        return {
            "status": "local_evidence_visible",
            "reason": "all_configured_local_evidence_paths_available",
            "missing_or_partial_phases": [],
        }


def build_dashboard_summary(project_root: Path | None = None) -> dict[str, Any]:
    return EvidenceDashboardService(project_root=project_root).build_summary()
