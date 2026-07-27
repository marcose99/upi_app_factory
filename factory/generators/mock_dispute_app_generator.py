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
DEFAULT_RECIPIENT_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)

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
PHASE42_READINESS_GATE_PATH = (
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase42/"
    "generated_application_local_run_readiness_gate.json"
)

CERTIFICATION_READINESS_TEST_OBLIGATIONS = [
    "unit",
    "integration",
    "contract",
    "negative",
    "resilience",
    "security",
    "performance_smoke",
    "replay",
    "audit",
]

PHASE42_REQUIRED_HEALTH_CHECKS = ("/health", "/startup", "/live", "/ready", "/metrics")


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


def validate_phase42_health_probe_contract(template_files: list[str]) -> None:
    health_script = "generated_application/scripts/health_check.py"
    api_main = "generated_application/app/interfaces/api/main.py"
    required_files = {health_script, api_main}
    if not required_files.issubset(set(template_files)):
        missing = sorted(required_files - set(template_files))
        raise ValueError(f"Phase 42 health probe contract missing template files: {missing}")

    health_text = (TEMPLATE_ROOT / health_script).read_text(encoding="utf-8")
    api_text = (TEMPLATE_ROOT / api_main).read_text(encoding="utf-8")
    if "@app.on_event" in api_text:
        raise ValueError("Phase 42 API template must use FastAPI lifespan handlers")
    if "lifespan=lifespan" not in api_text or "@asynccontextmanager" not in api_text:
        raise ValueError("Phase 42 API template must declare a lifespan context")
    for probe in PHASE42_REQUIRED_HEALTH_CHECKS:
        if probe not in health_text:
            raise ValueError(f"Phase 42 health_check.py does not exercise {probe}")
        if probe != "/metrics" and f'@app.get("{probe}")' not in api_text:
            raise ValueError(f"Phase 42 API template does not expose {probe}")
    if 'media_type="application/openmetrics-text' not in api_text:
        raise ValueError("Phase 42 API template does not expose OpenMetrics text metrics")


def validate_phase42_readiness_gate_contract() -> None:
    gate = read_json(PHASE42_READINESS_GATE_PATH)
    if gate.get("health_checks") != list(PHASE42_REQUIRED_HEALTH_CHECKS):
        raise ValueError("Phase 42 readiness gate health checks drifted from template")


def copy_templates(output_dir: Path, template_files: list[str]) -> list[GeneratedFile]:
    generated_files: list[GeneratedFile] = []

    for relative_path in template_files:
        source = TEMPLATE_ROOT / relative_path
        target = output_dir / "generated" / relative_path

        if not source.is_file():
            raise FileNotFoundError(f"Template missing: {source}")

        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or source.read_bytes() != target.read_bytes():
            shutil.copy2(source, target)
        else:
            shutil.copymode(source, target)

        generated_files.append(
            GeneratedFile(
                relative_path=relative_path,
                sha256=sha256_file(target),
                size_bytes=target.stat().st_size,
            )
        )

    return generated_files


def recipient_relative_path(generated_relative_path: str) -> Path:
    relative_path = Path(generated_relative_path)
    if relative_path.parts and relative_path.parts[0] == "generated_application":
        return Path(*relative_path.parts[1:])
    return relative_path


def propagate_to_recipient(
    *,
    generation: GenerationResult,
    recipient_root: Path = DEFAULT_RECIPIENT_ROOT,
) -> list[GeneratedFile]:
    recipient_root = recipient_root.resolve()
    propagated: list[GeneratedFile] = []

    for item in generation.generated_files:
        source = generation.output_dir / "generated" / item.relative_path
        target = recipient_root / recipient_relative_path(item.relative_path)
        if not source.is_file():
            raise FileNotFoundError(f"Generated file missing before propagation: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or source.read_bytes() != target.read_bytes():
            shutil.copy2(source, target)
        else:
            shutil.copymode(source, target)
        propagated.append(
            GeneratedFile(
                relative_path=target.relative_to(recipient_root).as_posix(),
                sha256=sha256_file(target),
                size_bytes=target.stat().st_size,
            )
        )

    return propagated


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
    validate_phase42_health_probe_contract([str(item) for item in template_files])
    validate_phase42_readiness_gate_contract()
    deep_structure_directories = template_manifest.get("deep_structure_directories", [])
    if not isinstance(deep_structure_directories, list):
        raise ValueError("Template manifest deep_structure_directories must be a list")
    pytest_collection_policy = template_manifest.get("pytest_collection_policy")
    if not isinstance(pytest_collection_policy, str) or "workspace/regeneration_runs" not in pytest_collection_policy:
        raise ValueError("Template manifest must define generated pytest collection policy")

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

    manifest_path = output_dir / "generation_manifest.json"
    generated_at_utc = datetime.now(timezone.utc).isoformat()
    if not clean and manifest_path.is_file():
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_generated_at_utc = existing_manifest.get("generated_at_utc")
        if isinstance(existing_generated_at_utc, str) and existing_generated_at_utc:
            generated_at_utc = existing_generated_at_utc

    generation_manifest = {
        "schema_version": "mock_dispute_app_generation_manifest.v1",
        "project": "upi_app_factory / UPI App Factory",
        "run_id": resolved_run_id,
        "generated_at_utc": generated_at_utc,
        "generation_mode": "deterministic_template_regeneration",
        "source_template_manifest": "factory/templates/mock_dispute_app/template_manifest.v1.json",
        "governance_inputs": REQUIRED_GOVERNANCE_FILES,
        "phase28_architecture_depth_inputs": [
            PHASE28_BLUEPRINT_PATH,
            PHASE28_POLICY_PATH,
            "prompts/phase28/generated_application_architecture_depth_prompt.md",
        ],
        "phase29_deep_structure_policy": PHASE29_POLICY_PATH,
        "phase29_deep_structure_policy_recorded": True,
        "pytest_collection_policy": pytest_collection_policy,
        "evidence_labels": sorted(REQUIRED_EVIDENCE_LABELS),
        "certification_readiness_test_obligations": (
            CERTIFICATION_READINESS_TEST_OBLIGATIONS
        ),
        "risky_actions_require_human_approval": [
            "risky self-evolution",
            "destructive actions",
            "merge",
            "tag",
            "release",
            "promotion",
            "push",
            "deployment",
            "live provider calls",
            "certification-related claims",
        ],
        "control_plane_policy": {
            "schema_version": "upi_app_factory.generated.control_plane_governance.v1",
            "typed_decisions": True,
            "deterministic_fail_closed": True,
            "approval_scope_binding": True,
            "approval_expiry_required": True,
            "approval_nonce_required": True,
            "approval_replay_rejected": True,
            "agent_schema_bound": True,
            "agent_loop_bound": 8,
            "least_privilege_required": True,
            "independent_verification_required": True,
            "silent_prompt_model_policy_test_self_modification_allowed": False,
            "portfolio_assessment_mode": "recommendation_only",
            "state_evidence_process_port_application_isolation": True,
        },
        "real_payment_calls_allowed": False,
        "live_provider_calls_allowed": False,
        "real_secrets_allowed": False,
        "deployment_allowed": False,
        "official_certification_claimed": False,
        "official_certification_granted": False,
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

    manifest_text = json.dumps(generation_manifest, indent=2) + "\n"
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")

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
    parser.add_argument(
        "--recipient-root",
        type=Path,
        default=None,
        help="Optionally propagate the declared generated files into a recipient generated_application root.",
    )
    args = parser.parse_args()

    result = generate(
        run_id=args.run_id,
        workspace_root=Path(args.workspace_root),
        clean=args.clean,
    )
    propagated_files = (
        propagate_to_recipient(generation=result, recipient_root=args.recipient_root)
        if args.recipient_root is not None
        else []
    )

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "output_dir": str(result.output_dir),
                "manifest_path": str(result.manifest_path),
                "generated_file_count": len(result.generated_files),
                "recipient_root": str(args.recipient_root) if args.recipient_root is not None else None,
                "propagated_file_count": len(propagated_files),
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
