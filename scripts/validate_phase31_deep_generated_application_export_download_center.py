#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, cast


APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path("policies/phase31_deep_generated_application_export_download_policy.json")
PROMPT_PATH = Path("prompts/phase31/deep_generated_application_export_download_prompt.md")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase31"
)
EXISTING_GENERATED_WORKSPACE = (
    PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
)

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    Path("scripts/export_phase31_deep_generated_application_bundle.py"),
    ARTIFACT_DIR / "deep_generated_application_export_download_gate.json",
    ARTIFACT_DIR / "deep_generated_application_export_download_audit.json",
    ARTIFACT_DIR / "operator_download_center_manifest.json",
]

REQUIRED_MODULE_DIRS = {
    "generated_application_export/generated_application/app/domain/",
    "generated_application_export/generated_application/app/application/",
    "generated_application_export/generated_application/app/infrastructure/",
    "generated_application_export/generated_application/app/interfaces/",
    "generated_application_export/generated_application/app/observability/",
    "generated_application_export/generated_application/app/security/",
    "generated_application_export/generated_application/app/tests/",
}

REQUIRED_EVIDENCE_FILES = {
    "generation_manifest.json",
    "export_manifest.json",
    "evidence/phase28_architecture_depth_inputs_summary.json",
    "evidence/phase29_deep_structure_policy_summary.json",
    "evidence/phase30_regeneration_certification_readiness_evidence_summary.json",
    "evidence/certification_ready_not_certified_boundary.json",
    "evidence/no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json",
    "evidence/mocked_simulated_ecosystem_boundary.json",
}

OFFICIAL_CERTIFICATION_CLAIM_PHRASES = {
    "officially certified",
    "official certification granted",
    "npci certified",
    "rbi approved",
    "bank approved",
    "production ready",
    "live payment capability",
}
LIVE_PROVIDER_ENABLEMENT_TERMS = {"requests.", "httpx.", "urllib.request", "boto3"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def zip_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in zip: {name}")
    return cast(dict[str, Any], value)


def snapshot_workspace() -> set[str]:
    if not EXISTING_GENERATED_WORKSPACE.exists():
        return set()
    return {
        str(path.relative_to(EXISTING_GENERATED_WORKSPACE))
        for path in EXISTING_GENERATED_WORKSPACE.rglob("*")
        if path.is_file()
    }


def run_export_script() -> tuple[Path, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, "scripts/export_phase31_deep_generated_application_bundle.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("Export script did not emit a JSON object")
    zip_path = PROJECT_ROOT / str(payload["zip_path"])
    return zip_path, cast(dict[str, Any], payload)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "deep_generated_application_export_download_gate.json")
    audit = load_json(ARTIFACT_DIR / "deep_generated_application_export_download_audit.json")
    center_manifest = load_json(ARTIFACT_DIR / "operator_download_center_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE31-GA-EXPORT-DOWNLOAD-CENTER-GATE":
        errors.append("Phase 31 policy missing mandatory export gate")
    if policy.get("destructive_workspace_replacement_allowed") is not False:
        errors.append("Phase 31 policy allows destructive workspace replacement")
    if policy.get("live_provider_calls_allowed") is not False:
        errors.append("Phase 31 policy allows live provider calls")
    if policy.get("real_secrets_allowed") is not False:
        errors.append("Phase 31 policy allows real secrets")
    if policy.get("deployment_allowed") is not False:
        errors.append("Phase 31 policy allows deployment")
    if policy.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Phase 31 policy changed certification boundary")
    if policy.get("official_certification_claimed") is not False:
        errors.append("Phase 31 policy claims official certification")
    if policy.get("official_certification_granted") is not False:
        errors.append("Phase 31 policy grants official certification")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 31 policy does not keep integrations mocked")

    for artifact, name in [(gate, "gate"), (audit, "audit"), (center_manifest, "manifest")]:
        if artifact.get("bundle_downloadable_zip_required") is not True:
            errors.append(f"Phase 31 {name} does not require downloadable zip")
        if artifact.get("destructive_workspace_replacement") is not False:
            errors.append(f"Phase 31 {name} allows destructive replacement")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 31 {name} claims official certification")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 31 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "Phase 29 deterministic generator",
        "certification_ready_not_certified",
        "mocked or simulated",
        "Do not destructively replace",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 31 prompt missing required phrase: {phrase}")


def validate_zip(errors: list[str], zip_path: Path, export_payload: dict[str, Any]) -> None:
    if not zip_path.is_file():
        errors.append(f"Export zip does not exist: {zip_path}")
        return

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        missing_dirs = sorted(
            required_dir
            for required_dir in REQUIRED_MODULE_DIRS
            if not any(name.startswith(required_dir) for name in names)
        )
        if missing_dirs:
            errors.append(f"Zip missing generated application module dirs: {missing_dirs}")

        missing_evidence = sorted(REQUIRED_EVIDENCE_FILES - names)
        if missing_evidence:
            errors.append(f"Zip missing evidence files: {missing_evidence}")
            return

        export_manifest = zip_json(archive, "export_manifest.json")
        generation_manifest = zip_json(archive, "generation_manifest.json")
        boundary = zip_json(archive, "evidence/certification_ready_not_certified_boundary.json")
        no_live = zip_json(
            archive,
            "evidence/no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json",
        )
        ecosystem = zip_json(archive, "evidence/mocked_simulated_ecosystem_boundary.json")

        expected_manifest_fields: dict[str, Any] = {
            "bundle_id": "phase31_deep_generated_application_bundle",
            "app_id": APP_ID,
            "phase": "phase31_deep_generated_application_export_download_center",
            "generator": "factory/generators/mock_dispute_app_generator.py",
            "generated_application_root": "generated_application_export/generated_application",
            "certification_boundary": "certification_ready_not_certified",
            "official_certification_claimed": False,
            "official_certification_granted": False,
            "live_provider_calls_allowed": False,
            "external_ecosystem_integrations": "mocked_or_simulated_only",
            "destructive_workspace_replacement": False,
        }
        for field, expected in expected_manifest_fields.items():
            if export_manifest.get(field) != expected:
                errors.append(f"Export manifest has invalid {field}: {export_manifest.get(field)}")
        if "generated_at_utc" not in export_manifest:
            errors.append("Export manifest missing generated_at_utc")
        if not export_manifest.get("evidence_files"):
            errors.append("Export manifest missing evidence_files")
        if not export_manifest.get("validation_commands"):
            errors.append("Export manifest missing validation_commands")
        if export_payload.get("existing_generated_workspace_destructively_replaced") is not False:
            errors.append("Export script reported generated workspace replacement")

        for manifest_name, manifest in [
            ("generation manifest", generation_manifest),
            ("boundary evidence", boundary),
            ("no-live evidence", no_live),
            ("ecosystem evidence", ecosystem),
        ]:
            if manifest.get("official_certification_claimed") is True:
                errors.append(f"{manifest_name} claims official certification")
            if manifest.get("official_certification_granted") is True:
                errors.append(f"{manifest_name} grants official certification")
            if manifest.get("live_provider_calls_allowed") is True:
                errors.append(f"{manifest_name} enables live provider calls")
            if manifest.get("real_secrets_allowed") is True:
                errors.append(f"{manifest_name} enables real secrets")
            if manifest.get("deployment_allowed") is True:
                errors.append(f"{manifest_name} enables deployment")
        if ecosystem.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
            errors.append("Ecosystem evidence does not preserve mocked/simulated boundary")

        for name in names:
            if name.endswith("/"):
                continue
            text = archive.read(name).decode("utf-8", errors="ignore").lower()
            for phrase in OFFICIAL_CERTIFICATION_CLAIM_PHRASES:
                if phrase in text:
                    errors.append(f"Zip includes official certification claim phrase: {phrase}")
            for term in LIVE_PROVIDER_ENABLEMENT_TERMS:
                if term in text:
                    errors.append(f"Zip includes live provider enablement term: {term}")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    errors.append(f"Zip includes real secret-like material in {name}")


def validate() -> list[str]:
    errors: list[str] = []
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 31 artifacts: {missing}"]

    validate_static_artifacts(errors)
    before = snapshot_workspace()
    try:
        zip_path, export_payload = run_export_script()
    except Exception as exc:
        return [f"Phase 31 export script failed: {exc}"]
    after = snapshot_workspace()
    if before != after:
        errors.append("Existing generated workspace file list changed during export validation")
    validate_zip(errors, zip_path, export_payload)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2))
        return 1
    print("Phase 31 deep generated application export/download center validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
