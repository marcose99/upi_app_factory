from __future__ import annotations

import json
import zipfile
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHASE32 = "phase32_operator_portal_download_center_integration"

ExportRunner = Callable[[], dict[str, Any]]

REQUIRED_ZIP_MEMBERS = {
    "export_manifest.json",
    "generation_manifest.json",
    "evidence/phase28_architecture_depth_inputs_summary.json",
    "evidence/phase29_deep_structure_policy_summary.json",
    "evidence/phase30_regeneration_certification_readiness_evidence_summary.json",
    "evidence/certification_ready_not_certified_boundary.json",
    "evidence/no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json",
    "evidence/mocked_simulated_ecosystem_boundary.json",
}


def _load_zip_json(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    value = json.loads(archive.read(member).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in bundle member: {member}")
    return cast(dict[str, Any], value)


def _default_export_runner() -> dict[str, Any]:
    script_path = PROJECT_ROOT / "scripts/export_phase31_deep_generated_application_bundle.py"
    spec = importlib.util.spec_from_file_location("phase31_export_bundle", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Phase 31 export script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    export_function = getattr(module, "export_bundle", None)
    if not callable(export_function):
        raise RuntimeError("Phase 31 export script does not expose export_bundle")
    result = export_function(clean=True)
    if not isinstance(result, dict):
        raise RuntimeError("Phase 31 export_bundle did not return a JSON-like object")
    return cast(dict[str, Any], result)


class DownloadCenterService:
    """Portal-ready local download center for governed generated app exports."""

    def __init__(self, export_runner: ExportRunner | None = None) -> None:
        self._export_runner = export_runner or _default_export_runner

    def trigger_governed_export(self) -> dict[str, Any]:
        export_payload = self._export_runner()
        zip_path = self._resolve_project_path(export_payload, "zip_path")
        manifest_path = self._resolve_project_path(export_payload, "manifest_path")
        generation_manifest_path = self._resolve_project_path(
            export_payload,
            "generation_manifest_path",
        )

        if export_payload.get("existing_generated_workspace_destructively_replaced") is not False:
            raise RuntimeError("Phase 31 export reported destructive generated workspace replacement")
        if not zip_path.is_file():
            raise RuntimeError(f"Phase 31 export did not create a zip bundle: {zip_path}")
        if not manifest_path.is_file():
            raise RuntimeError(f"Phase 31 export manifest is not available: {manifest_path}")
        if not generation_manifest_path.is_file():
            raise RuntimeError(
                f"Phase 31 generation manifest is not available: {generation_manifest_path}"
            )

        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            missing = sorted(REQUIRED_ZIP_MEMBERS - names)
            if missing:
                raise RuntimeError(f"Phase 31 export bundle is missing required members: {missing}")

            export_manifest = _load_zip_json(archive, "export_manifest.json")
            generation_manifest = _load_zip_json(archive, "generation_manifest.json")
            evidence_summaries = {
                member: _load_zip_json(archive, member)
                for member in sorted(name for name in names if name.startswith("evidence/"))
                if member.endswith(".json")
            }

        self._validate_safety_boundary(export_manifest, evidence_summaries)

        bundle_metadata = {
            "bundle_id": export_manifest["bundle_id"],
            "app_id": export_manifest["app_id"],
            "phase31_export_phase": export_manifest["phase"],
            "phase32_service_phase": PHASE32,
            "zip_size_bytes": zip_path.stat().st_size,
            "included_files_count": export_manifest["included_files_count"],
            "certification_boundary": export_manifest["certification_boundary"],
            "official_certification_claimed": export_manifest[
                "official_certification_claimed"
            ],
            "live_provider_calls_allowed": export_manifest["live_provider_calls_allowed"],
            "real_secrets_allowed": export_manifest["real_secrets_allowed"],
            "deployment_allowed": export_manifest["deployment_allowed"],
            "external_ecosystem_integrations": export_manifest[
                "external_ecosystem_integrations"
            ],
        }
        relative_zip_path = zip_path.relative_to(PROJECT_ROOT).as_posix()
        return {
            "status": "export_ready",
            "phase31_export_invoked": True,
            "bundle_metadata": bundle_metadata,
            "bundle_path": relative_zip_path,
            "local_bundle_path": str(zip_path),
            "download_ready_path": str(zip_path),
            "export_manifest_path": str(manifest_path),
            "generation_manifest_path": str(generation_manifest_path),
            "export_manifest": export_manifest,
            "generation_manifest": generation_manifest,
            "evidence_summaries": evidence_summaries,
            "safety_boundaries": {
                "live_provider_calls_allowed": False,
                "real_secrets_allowed": False,
                "deployment_allowed": False,
                "destructive_workspace_replacement_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
                "certification_boundary": "certification_ready_not_certified",
                "official_certification_claimed": False,
                "official_certification_granted": False,
                "production_readiness_claimed": False,
            },
        }

    def get_manifest(self, download_center_result: dict[str, Any]) -> dict[str, Any]:
        manifest = download_center_result.get("export_manifest")
        if not isinstance(manifest, dict):
            raise ValueError("Download center result does not include an export manifest")
        return cast(dict[str, Any], manifest)

    def get_evidence_summaries(
        self,
        download_center_result: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        evidence = download_center_result.get("evidence_summaries")
        if not isinstance(evidence, dict):
            raise ValueError("Download center result does not include evidence summaries")
        return cast(dict[str, dict[str, Any]], evidence)

    def _resolve_project_path(self, export_payload: dict[str, Any], key: str) -> Path:
        value = export_payload.get(key)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"Phase 31 export payload missing path: {key}")
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    def _validate_safety_boundary(
        self,
        export_manifest: dict[str, Any],
        evidence_summaries: dict[str, dict[str, Any]],
    ) -> None:
        expected_fields: dict[str, Any] = {
            "certification_boundary": "certification_ready_not_certified",
            "official_certification_claimed": False,
            "official_certification_granted": False,
            "live_provider_calls_allowed": False,
            "real_secrets_allowed": False,
            "deployment_allowed": False,
            "external_ecosystem_integrations": "mocked_or_simulated_only",
            "destructive_workspace_replacement": False,
        }
        for field, expected in expected_fields.items():
            if export_manifest.get(field) != expected:
                raise RuntimeError(
                    f"Phase 31 export manifest violates download center boundary: {field}"
                )

        for evidence_name, evidence in evidence_summaries.items():
            for field in [
                "official_certification_claimed",
                "official_certification_granted",
                "live_provider_calls_allowed",
                "real_secrets_allowed",
                "deployment_allowed",
            ]:
                if evidence.get(field) is True:
                    raise RuntimeError(
                        f"Phase 31 evidence violates download center boundary: "
                        f"{evidence_name} {field}"
                    )


def trigger_export() -> dict[str, Any]:
    return DownloadCenterService().trigger_governed_export()
