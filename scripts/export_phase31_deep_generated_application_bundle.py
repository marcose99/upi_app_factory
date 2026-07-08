#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from factory.generators.mock_dispute_app_generator import generate


APP_ID = "upi_dispute_resolution"
PHASE = "phase31_deep_generated_application_export_download_center"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = (
    PROJECT_ROOT
    / "workspace/factory_generated"
    / APP_ID
    / "export_bundles"
    / "phase31"
)
EXPORT_WORKSPACE_ROOT = EXPORT_ROOT / "workspace"
BUNDLE_STAGING_ROOT = EXPORT_ROOT / "staging"
GENERATED_WORKSPACE_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
)
BUNDLE_ID = "phase31_deep_generated_application_bundle"
RUN_ID = "phase31_deep_generated_application_export"
ZIP_NAME = f"{BUNDLE_ID}.zip"

GENERATOR_PATH = "factory/generators/mock_dispute_app_generator.py"
PHASE28_INPUTS = [
    "factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json",
    "policies/phase28_generated_application_architecture_depth_policy.json",
    "prompts/phase28/generated_application_architecture_depth_prompt.md",
]
PHASE29_POLICY_PATH = "policies/phase29_generated_application_deep_structure_policy.json"
PHASE30_EVIDENCE_FILES = [
    "policies/phase30_deep_generated_application_regeneration_policy.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/deep_generated_application_regeneration_audit.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/controlled_regeneration_output_manifest.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/certification_readiness_test_obligation_matrix.json",
]

VALIDATION_COMMANDS = [
    "python scripts/validate_phase31_deep_generated_application_export_download_center.py",
    "python scripts/validate_phase30_deep_generated_application_regeneration.py",
    "python scripts/validate_phase29_generated_application_deep_structure_generator.py",
    "python scripts/validate_phase28_generated_application_architecture_depth_blueprint.py",
    "python -m pytest tests/test_phase31_deep_generated_application_export_download_center.py",
]


def load_json(relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {relative_path}")
    return cast(dict[str, Any], value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_fingerprint(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    fingerprints: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        fingerprints[str(path.relative_to(root))] = sha256_file(path)
    return fingerprints


def git_value(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def copy_relative_file(relative_path: str, destination_root: Path) -> str:
    source = PROJECT_ROOT / relative_path
    if not source.is_file():
        raise FileNotFoundError(relative_path)
    destination = destination_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return str(destination.relative_to(destination_root))


def build_evidence(staging_root: Path, generation_manifest: dict[str, Any]) -> list[str]:
    evidence_root = staging_root / "evidence"

    phase28_boundary = load_json(
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/certification_boundary.json"
    )
    phase29_policy = load_json(PHASE29_POLICY_PATH)
    phase29_audit = load_json(
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_audit.json"
    )
    phase30_policy = load_json("policies/phase30_deep_generated_application_regeneration_policy.json")
    phase30_audit = load_json(
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30/deep_generated_application_regeneration_audit.json"
    )

    evidence_payloads = {
        "phase28_architecture_depth_inputs_summary.json": {
            "phase": "phase28_generated_application_architecture_depth_blueprint",
            "inputs": PHASE28_INPUTS,
            "certification_boundary": phase28_boundary["certification_boundary"],
            "live_provider_calls_allowed": phase28_boundary["live_provider_calls_allowed"],
            "external_ecosystem_integrations": phase28_boundary[
                "external_ecosystem_integrations"
            ],
        },
        "phase29_deep_structure_policy_summary.json": {
            "phase": "phase29_generated_application_deep_structure_generator",
            "policy": PHASE29_POLICY_PATH,
            "phase28_blueprint_required_as_generator_input": phase29_policy[
                "phase28_blueprint_required_as_generator_input"
            ],
            "deep_structure_generator_ready": phase29_audit["factory_generation_layer_updated"],
            "certification_boundary": phase29_policy["certification_boundary"],
            "live_provider_calls_allowed": phase29_policy["live_provider_calls_allowed"],
            "external_ecosystem_integrations": phase29_policy[
                "external_ecosystem_integrations"
            ],
        },
        "phase30_regeneration_certification_readiness_evidence_summary.json": {
            "phase": "phase30_deep_generated_application_regeneration_validation",
            "phase29_generator_output_required": phase30_policy[
                "phase29_generator_output_required"
            ],
            "controlled_output_strategy": phase30_audit["controlled_output_strategy"],
            "destructive_workspace_replacement_allowed": phase30_policy[
                "destructive_workspace_replacement_allowed"
            ],
            "certification_readiness_test_obligations": phase30_policy[
                "certification_readiness_test_obligations"
            ],
            "certification_boundary": phase30_policy["certification_boundary"],
            "official_certification_claimed": phase30_policy[
                "official_certification_claimed"
            ],
            "official_certification_granted": phase30_policy[
                "official_certification_granted"
            ],
        },
        "certification_ready_not_certified_boundary.json": {
            "certification_boundary": "certification_ready_not_certified",
            "official_certification_claimed": False,
            "official_certification_granted": False,
            "production_readiness_claimed": False,
            "deployment_allowed": False,
        },
        "no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json": {
            "live_provider_calls_allowed": False,
            "real_secrets_allowed": False,
            "deployment_allowed": False,
            "official_certification_claimed": False,
            "official_certification_granted": False,
            "real_payment_calls_allowed": False,
        },
        "mocked_simulated_ecosystem_boundary.json": {
            "external_ecosystem_integrations": "mocked_or_simulated_only",
            "mock_boundary": True,
            "real_npci_rbi_bank_psp_payment_rail_integration_allowed": False,
        },
        "generated_application_generation_manifest_summary.json": {
            "run_id": generation_manifest["run_id"],
            "generation_mode": generation_manifest["generation_mode"],
            "phase28_architecture_depth_inputs": generation_manifest[
                "phase28_architecture_depth_inputs"
            ],
            "phase29_deep_structure_policy": generation_manifest[
                "phase29_deep_structure_policy"
            ],
            "generated_file_count": len(generation_manifest["generated_files"]),
            "certification_boundary": generation_manifest["certification_boundary"],
        },
        "source_evidence_file_index.json": {
            "referenced_phase28_inputs": PHASE28_INPUTS,
            "referenced_phase29_policy": PHASE29_POLICY_PATH,
            "referenced_phase30_evidence_files": PHASE30_EVIDENCE_FILES,
            "raw_source_files_copied_into_bundle": False,
        },
    }

    evidence_files: list[str] = []
    for filename, payload in evidence_payloads.items():
        path = evidence_root / filename
        write_json(path, payload)
        evidence_files.append(str(path.relative_to(staging_root)))

    return sorted(evidence_files)


def zip_directory(source_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_dir()):
            archive_info = zipfile.ZipInfo(path.relative_to(source_root).as_posix() + "/")
            archive.writestr(archive_info, "")
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(source_root).as_posix())


def export_bundle(*, clean: bool = True) -> dict[str, Any]:
    before_fingerprint = workspace_fingerprint(GENERATED_WORKSPACE_ROOT)

    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    if clean:
        for safe_path in [EXPORT_WORKSPACE_ROOT / RUN_ID, BUNDLE_STAGING_ROOT / BUNDLE_ID]:
            if safe_path.exists():
                shutil.rmtree(safe_path)

    generation_result = generate(
        run_id=RUN_ID,
        workspace_root=EXPORT_WORKSPACE_ROOT,
        clean=clean,
    )
    generation_manifest = load_json(
        str(generation_result.manifest_path.relative_to(PROJECT_ROOT))
    )

    staging_root = BUNDLE_STAGING_ROOT / BUNDLE_ID
    if staging_root.exists() and clean:
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    generated_source = generation_result.output_dir / "generated"
    generated_destination = staging_root / "generated_application_export"
    shutil.copytree(generated_source, generated_destination, dirs_exist_ok=True)
    shutil.copyfile(generation_result.manifest_path, staging_root / "generation_manifest.json")

    evidence_files = build_evidence(staging_root, generation_manifest)

    generated_files_count = sum(1 for path in generated_destination.rglob("*") if path.is_file())
    export_manifest = {
        "bundle_id": BUNDLE_ID,
        "app_id": APP_ID,
        "phase": PHASE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_branch": git_value(["rev-parse", "--abbrev-ref", "HEAD"]),
        "source_commit": git_value(["rev-parse", "HEAD"]),
        "generator": GENERATOR_PATH,
        "generated_application_root": "generated_application_export/generated_application",
        "included_files_count": generated_files_count + len(evidence_files) + 2,
        "evidence_files": evidence_files,
        "validation_commands": VALIDATION_COMMANDS,
        "certification_boundary": "certification_ready_not_certified",
        "official_certification_claimed": False,
        "official_certification_granted": False,
        "live_provider_calls_allowed": False,
        "external_ecosystem_integrations": "mocked_or_simulated_only",
        "destructive_workspace_replacement": False,
        "real_secrets_allowed": False,
        "deployment_allowed": False,
        "mocked_or_simulated_ecosystem_only": True,
        "source_generation_manifest": "generation_manifest.json",
    }
    write_json(staging_root / "export_manifest.json", export_manifest)

    zip_path = EXPORT_ROOT / ZIP_NAME
    zip_directory(staging_root, zip_path)

    after_fingerprint = workspace_fingerprint(GENERATED_WORKSPACE_ROOT)
    existing_workspace_replaced = before_fingerprint != after_fingerprint
    result = {
        "bundle_id": BUNDLE_ID,
        "zip_path": str(zip_path.relative_to(PROJECT_ROOT)),
        "staging_root": str(staging_root.relative_to(PROJECT_ROOT)),
        "export_workspace": str(generation_result.output_dir.relative_to(PROJECT_ROOT)),
        "manifest_path": str((staging_root / "export_manifest.json").relative_to(PROJECT_ROOT)),
        "generation_manifest_path": str(
            (staging_root / "generation_manifest.json").relative_to(PROJECT_ROOT)
        ),
        "existing_generated_workspace_destructively_replaced": existing_workspace_replaced,
        "included_files_count": export_manifest["included_files_count"],
    }
    if existing_workspace_replaced:
        raise RuntimeError("Existing generated workspace changed during Phase 31 export")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a governed local Phase 31 generated application export bundle."
    )
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    result = export_bundle(clean=not args.no_clean)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
