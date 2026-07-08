from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = PROJECT_ROOT / "factory/templates/mock_dispute_app"
DEFAULT_WORKSPACE_ROOT = PROJECT_ROOT / "workspace/regeneration_runs"

REQUIRED_EVIDENCE_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_GOVERNANCE_FILES = [
    "factory_governance/phase2/upi_dispute_requirements.v1.json",
    "factory_governance/phase2/mock_external_system_contracts.v1.json",
    "factory_governance/phase3/architecture_design_contract.v1.json",
    "factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json",
    "policies/phase28_generated_application_architecture_depth_policy.json",
]

PHASE28_BLUEPRINT_PATH = (
    "factory_governance/generated_application_architecture_depth/"
    "phase28_architecture_depth_blueprint.v1.json"
)
PHASE28_POLICY_PATH = "policies/phase28_generated_application_architecture_depth_policy.json"

PHASE29_POLICY_PATH = "policies/phase29_generated_application_deep_structure_policy.json"


@dataclass(frozen=True)
class GeneratedFile:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class GenerationResult:
    run_id: str
    output_dir: Path
    manifest_path: Path
    generated_files: list[GeneratedFile]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {relative_path}")
    return value


def validate_governance_inputs() -> None:
    requirements = read_json(
        "factory_governance/phase2/upi_dispute_requirements.v1.json"
    )
    if requirements.get("real_payment_calls_allowed") is not False:
        raise ValueError("Phase 2 requirements must forbid real payment calls")

    requirement_labels = set(requirements.get("evidence_labels_required", []))
    if not REQUIRED_EVIDENCE_LABELS.issubset(requirement_labels):
        raise ValueError("Phase 2 requirements are missing required evidence labels")

    ecosystem = read_json(
        "factory_governance/phase2/mock_external_system_contracts.v1.json"
    )
    systems = ecosystem.get("systems", [])
    if not isinstance(systems, list) or len(systems) < 4:
        raise ValueError("Mock ecosystem must define at least four systems")

    for system in systems:
        if not isinstance(system, dict):
            raise ValueError("Mock ecosystem system entries must be objects")
        if system.get("boundary") != "MOCK_BOUNDARY":
            raise ValueError("Every external system must be a MOCK_BOUNDARY")
        if system.get("data_label") != "SYNTHETIC_DATA":
            raise ValueError("Every external system must use SYNTHETIC_DATA")
        if system.get("real_integration_allowed") is not False:
            raise ValueError("Every external system must forbid real integration")

    architecture = read_json(
        "factory_governance/phase3/architecture_design_contract.v1.json"
    )
    if architecture.get("selected_architecture") != (
        "lightweight_fastapi_modular_mock_adapters"
    ):
        raise ValueError("Architecture contract selected architecture is invalid")
    if architecture.get("model_provider") != "OpenAI":
        raise ValueError("Architecture contract must keep OpenAI as model provider")
    if architecture.get("real_payment_calls_allowed") is not False:
        raise ValueError("Architecture contract must forbid real payment calls")

    phase28_blueprint = read_json(PHASE28_BLUEPRINT_PATH)
    if phase28_blueprint.get("status") != "ARCHITECTURE_DEPTH_BLUEPRINT_REQUIRED":
        raise ValueError("Phase 28 architecture-depth blueprint must be required")
    phase28_gate = phase28_blueprint.get("architecture_depth_gate", {})
    if phase28_gate.get("required_before_application_generation_success") is not True:
        raise ValueError("Phase 28 architecture-depth gate must block generation success")
    phase28_boundary = phase28_blueprint.get("boundary_rules", {})
    if phase28_boundary.get("certification_boundary") != "certification_ready_not_certified":
        raise ValueError("Phase 28 boundary must remain certification_ready_not_certified")
    if phase28_boundary.get("live_provider_calls_allowed") is not False:
        raise ValueError("Phase 28 boundary must forbid live provider calls")
    if phase28_boundary.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        raise ValueError("Phase 28 boundary must keep external ecosystem integrations mocked")

    phase28_policy = read_json(PHASE28_POLICY_PATH)
    if phase28_policy.get("required_before_generation_success") is not True:
        raise ValueError("Phase 28 policy must be required before generation success")

    phase29_policy = read_json(PHASE29_POLICY_PATH)
    if phase29_policy.get("phase28_blueprint_required_as_generator_input") is not True:
        raise ValueError("Phase 29 policy must require Phase 28 blueprint as generator input")
    if phase29_policy.get("live_provider_calls_allowed") is not False:
        raise ValueError("Phase 29 policy must forbid live provider calls")
    if phase29_policy.get("certification_boundary") != "certification_ready_not_certified":
        raise ValueError("Phase 29 policy must preserve certification-ready-not-certified")


def load_template_manifest() -> dict[str, Any]:
    path = TEMPLATE_ROOT / "template_manifest.v1.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Template manifest root must be object")
    return value


def copy_templates(output_dir: Path, template_files: list[str]) -> list[GeneratedFile]:
    generated_files: list[GeneratedFile] = []

    for relative_path in template_files:
        source = TEMPLATE_ROOT / relative_path
        target = output_dir / "generated" / relative_path

        if not source.is_file():
            raise FileNotFoundError(f"Template missing: {source}")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

        generated_files.append(
            GeneratedFile(
                relative_path=relative_path,
                sha256=sha256_file(target),
                size_bytes=target.stat().st_size,
            )
        )

    return generated_files


def create_deep_structure_directories(output_dir: Path, directories: list[str]) -> None:
    for relative_path in directories:
        if not relative_path.endswith("/"):
            raise ValueError(f"Deep-structure directory must end with '/': {relative_path}")
        (output_dir / "generated" / relative_path).mkdir(parents=True, exist_ok=True)


def generate(
    *,
    run_id: str | None = None,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    clean: bool = False,
) -> GenerationResult:
    validate_governance_inputs()

    template_manifest = load_template_manifest()
    template_files = template_manifest.get("template_files", [])
    if not isinstance(template_files, list) or not template_files:
        raise ValueError("Template manifest must define template_files")
    deep_structure_directories = template_manifest.get("deep_structure_directories", [])
    if not isinstance(deep_structure_directories, list):
        raise ValueError("Template manifest deep_structure_directories must be a list")

    resolved_run_id = (
        run_id
        if run_id is not None
        else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )

    output_dir = workspace_root / resolved_run_id

    if output_dir.exists() and clean:
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    create_deep_structure_directories(
        output_dir,
        [str(item) for item in deep_structure_directories],
    )
    generated_files = copy_templates(output_dir, [str(item) for item in template_files])

    generation_manifest = {
        "schema_version": "mock_dispute_app_generation_manifest.v1",
        "project": "FactoryFromNothing / UPI Dispute Resolution Factory",
        "run_id": resolved_run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "deterministic_template_regeneration",
        "source_template_manifest": "factory/templates/mock_dispute_app/template_manifest.v1.json",
        "governance_inputs": REQUIRED_GOVERNANCE_FILES,
        "phase28_architecture_depth_inputs": [
            PHASE28_BLUEPRINT_PATH,
            PHASE28_POLICY_PATH,
            "prompts/phase28/generated_application_architecture_depth_prompt.md",
        ],
        "phase29_deep_structure_policy": PHASE29_POLICY_PATH,
        "evidence_labels": sorted(REQUIRED_EVIDENCE_LABELS),
        "real_payment_calls_allowed": False,
        "live_provider_calls_allowed": False,
        "certification_boundary": "certification_ready_not_certified",
        "external_ecosystem_integrations": "mocked_or_simulated_only",
        "deep_structure_directories": [str(item) for item in deep_structure_directories],
        "generated_files": [
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in generated_files
        ],
    }

    manifest_path = output_dir / "generation_manifest.json"
    manifest_path.write_text(
        json.dumps(generation_manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return GenerationResult(
        run_id=resolved_run_id,
        output_dir=output_dir,
        manifest_path=manifest_path,
        generated_files=generated_files,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate mock dispute app artifacts into workspace."
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--workspace-root",
        default=str(DEFAULT_WORKSPACE_ROOT),
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    result = generate(
        run_id=args.run_id,
        workspace_root=Path(args.workspace_root),
        clean=args.clean,
    )

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "output_dir": str(result.output_dir),
                "manifest_path": str(result.manifest_path),
                "generated_file_count": len(result.generated_files),
                "generated_files": [
                    {
                        "relative_path": item.relative_path,
                        "sha256": item.sha256,
                        "size_bytes": item.size_bytes,
                    }
                    for item in result.generated_files
                ],
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
