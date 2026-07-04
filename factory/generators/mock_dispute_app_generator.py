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
]


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

    resolved_run_id = (
        run_id
        if run_id is not None
        else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )

    output_dir = workspace_root / resolved_run_id

    if output_dir.exists() and clean:
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    generated_files = copy_templates(output_dir, [str(item) for item in template_files])

    generation_manifest = {
        "schema_version": "mock_dispute_app_generation_manifest.v1",
        "project": "FactoryFromNothing / UPI Dispute Resolution Factory",
        "run_id": resolved_run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "deterministic_template_regeneration",
        "source_template_manifest": "factory/templates/mock_dispute_app/template_manifest.v1.json",
        "governance_inputs": REQUIRED_GOVERNANCE_FILES,
        "evidence_labels": sorted(REQUIRED_EVIDENCE_LABELS),
        "real_payment_calls_allowed": False,
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
