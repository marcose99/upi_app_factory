#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.download_center import DownloadCenterService


APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path("policies/phase32_operator_portal_download_center_policy.json")
PROMPT_PATH = Path("prompts/phase32/operator_portal_download_center_prompt.md")
SERVICE_PATH = Path("factory/operator_portal/download_center.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase32"
)
EXISTING_GENERATED_WORKSPACE = (
    PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
)

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    SERVICE_PATH,
    ARTIFACT_DIR / "operator_portal_download_center_gate.json",
    ARTIFACT_DIR / "operator_portal_download_center_audit.json",
    ARTIFACT_DIR / "operator_portal_download_center_manifest.json",
]

REQUIRED_EVIDENCE_NAMES = {
    "evidence/phase28_architecture_depth_inputs_summary.json",
    "evidence/phase29_deep_structure_policy_summary.json",
    "evidence/phase30_regeneration_certification_readiness_evidence_summary.json",
    "evidence/certification_ready_not_certified_boundary.json",
    "evidence/no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json",
    "evidence/mocked_simulated_ecosystem_boundary.json",
}

LIVE_PROVIDER_ENABLEMENT_TERMS = {"requests.", "urllib.request", "boto3", "google.cloud"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def snapshot_workspace() -> dict[str, str]:
    if not EXISTING_GENERATED_WORKSPACE.exists():
        return {}
    return {
        str(path.relative_to(EXISTING_GENERATED_WORKSPACE)): str(path.stat().st_size)
        for path in EXISTING_GENERATED_WORKSPACE.rglob("*")
        if path.is_file()
    }


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "operator_portal_download_center_gate.json")
    audit = load_json(ARTIFACT_DIR / "operator_portal_download_center_audit.json")
    manifest = load_json(ARTIFACT_DIR / "operator_portal_download_center_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE32-OPERATOR-PORTAL-DOWNLOAD-CENTER-GATE":
        errors.append("Phase 32 policy missing mandatory portal/download center gate")
    if policy.get("phase31_export_capability_required") != (
        "scripts/export_phase31_deep_generated_application_bundle.py"
    ):
        errors.append("Phase 32 policy does not require the Phase 31 export capability")
    if policy.get("portal_success_requires_existing_validated_bundle") is not True:
        errors.append("Phase 32 policy does not require validated bundle success")

    for artifact, name in [(policy, "policy"), (gate, "gate"), (audit, "audit"), (manifest, "manifest")]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 32 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 32 {name} claims official certification")
        if artifact.get("official_certification_granted") is not False:
            errors.append(f"Phase 32 {name} grants official certification")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "destructive_workspace_replacement_allowed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 32 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 32 policy does not keep ecosystem integrations mocked")
    if policy.get("production_readiness_claimed") is not False:
        errors.append("Phase 32 policy claims production readiness")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 32 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "Phase 31",
        "certification_ready_not_certified",
        "mocked or simulated",
        "must never fake generation",
        "Do not destructively replace",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 32 prompt missing required phrase: {phrase}")

    if "export_bundle" not in service_source:
        errors.append("Download center service does not wrap Phase 31 export_bundle")
    if "phase31_export_invoked" not in service_source:
        errors.append("Download center service does not expose Phase 31 invocation evidence")
    for term in LIVE_PROVIDER_ENABLEMENT_TERMS:
        if term in service_source:
            errors.append(f"Download center service includes live provider enablement term: {term}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(service_source):
            errors.append("Download center service includes secret-like material")


def validate_portal_export(errors: list[str]) -> dict[str, Any] | None:
    before = snapshot_workspace()
    try:
        result = DownloadCenterService().trigger_governed_export()
    except Exception as exc:
        errors.append(f"Download center service failed to trigger Phase 31 export: {exc}")
        return None
    after = snapshot_workspace()
    if before != after:
        errors.append("Existing generated workspace changed during portal export validation")

    zip_path = Path(str(result.get("download_ready_path", "")))
    if not zip_path.is_file():
        errors.append(f"Download-ready zip path does not exist: {zip_path}")
    if result.get("phase31_export_invoked") is not True:
        errors.append("Download center did not report Phase 31 export invocation")
    if result.get("status") != "export_ready":
        errors.append("Download center did not return export_ready status")

    export_manifest = result.get("export_manifest")
    generation_manifest = result.get("generation_manifest")
    evidence_summaries = result.get("evidence_summaries")
    bundle_metadata = result.get("bundle_metadata")

    if not isinstance(bundle_metadata, dict) or not bundle_metadata:
        errors.append("Download center did not return bundle metadata")
    if not isinstance(export_manifest, dict):
        errors.append("Download center did not expose export_manifest.json contents")
        export_manifest = {}
    if not isinstance(generation_manifest, dict):
        errors.append("Download center did not expose generation_manifest.json contents")
        generation_manifest = {}
    if not isinstance(evidence_summaries, dict):
        errors.append("Download center did not expose evidence summaries")
        evidence_summaries = {}

    missing_evidence = sorted(REQUIRED_EVIDENCE_NAMES - set(evidence_summaries))
    if missing_evidence:
        errors.append(f"Download center missing evidence summaries: {missing_evidence}")

    for source_name, source in [
        ("export manifest", cast(dict[str, Any], export_manifest)),
        ("generation manifest", cast(dict[str, Any], generation_manifest)),
        ("bundle metadata", cast(dict[str, Any], bundle_metadata or {})),
    ]:
        if source.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"{source_name} does not preserve certification-ready-not-certified")
        if source.get("official_certification_claimed") is True:
            errors.append(f"{source_name} claims official certification")
        if source.get("official_certification_granted") is True:
            errors.append(f"{source_name} grants official certification")
        if source.get("live_provider_calls_allowed") is True:
            errors.append(f"{source_name} enables live provider calls")
        if source.get("real_secrets_allowed") is True:
            errors.append(f"{source_name} enables real secrets")
        if source.get("deployment_allowed") is True:
            errors.append(f"{source_name} enables deployment")

    for evidence_name, evidence in cast(dict[str, dict[str, Any]], evidence_summaries).items():
        if evidence.get("official_certification_claimed") is True:
            errors.append(f"{evidence_name} claims official certification")
        if evidence.get("official_certification_granted") is True:
            errors.append(f"{evidence_name} grants official certification")
        if evidence.get("live_provider_calls_allowed") is True:
            errors.append(f"{evidence_name} enables live provider calls")
        if evidence.get("real_secrets_allowed") is True:
            errors.append(f"{evidence_name} enables real secrets")
        if evidence.get("deployment_allowed") is True:
            errors.append(f"{evidence_name} enables deployment")

    return result


def validate_fake_success_rejected(errors: list[str]) -> None:
    def fake_export_runner() -> dict[str, Any]:
        return {
            "bundle_id": "fake",
            "zip_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake.zip",
            "manifest_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake/export_manifest.json",
            "generation_manifest_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake/generation_manifest.json",
            "existing_generated_workspace_destructively_replaced": False,
        }

    try:
        DownloadCenterService(export_runner=fake_export_runner).trigger_governed_export()
    except RuntimeError:
        return
    errors.append("Download center accepted fake export success without an existing valid bundle")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 32 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_portal_export(errors)
    validate_fake_success_rejected(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2))
        return 1
    print("Phase 32 operator portal download center integration validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
