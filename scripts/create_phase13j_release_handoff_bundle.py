#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13J"
RUN_ID = "first_governed_generation_run_001"
BASELINE_TAG = "v0.13.8-release-readiness-operator-acceptance"
APP_WORKSPACE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DIR = APP_WORKSPACE / "lifecycle_artifacts" / "phase13j"
BUNDLE_DIR = APP_WORKSPACE / "release_handoff_bundle" / "phase13j"

TRUTH_BOUNDARY = (
    "This handoff bundle describes a locally runnable, deterministic governed factory release. "
    "Local deterministic execution remains the default. LangGraph/OpenAI execution remains detected "
    "and policy-gated, not falsely claimed as active."
)

OPERATOR_COMMANDS = [
    "./factoryctl status",
    "./factoryctl adapters",
    "./factoryctl validate --quick",
    "./factoryctl validate",
    "./factoryctl portals",
    "./factoryctl handover",
    "./factoryctl logs",
]

REQUIRED_RELEASE_FILES = [
    "README.md",
    "factoryctl",
    "scripts/factory_cli.py",
    "docs/phase13d/agent_adapter_execution_layer.md",
    "docs/phase13e/factory_cli_operator_surface.md",
    "docs/phase13f/operator_handover_closure.md",
    "docs/phase13g/readonly_validation_drift_guardrails.md",
    "docs/phase13h/release_state_lineage_registry.md",
    "docs/phase13i/release_readiness_operator_acceptance.md",
    "scripts/validate_phase13d_agent_adapter_execution.py",
    "scripts/validate_phase13e_factory_cli_operator_surface.py",
    "scripts/validate_phase13f_operator_handover_closure.py",
    "scripts/validate_phase13g_readonly_validation_guardrails.py",
    "scripts/validate_phase13h_release_state_lineage.py",
    "scripts/validate_phase13i_release_readiness.py",
]


class BundleError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0


def required_file_entries() -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for relative_path in REQUIRED_RELEASE_FILES:
        path = PROJECT_ROOT / relative_path
        exists = path.is_file()
        checksum = sha256_file(path) if exists else None
        if not exists:
            errors.append(f"Missing required release file: {relative_path}")
        entries.append(
            {
                "path": relative_path,
                "exists": exists,
                "sha256": checksum,
            }
        )
    return entries, errors


def markdown_list(items: list[str]) -> str:
    return "\n".join(f"- `{item}`" for item in items)


def build_manifest() -> dict[str, Any]:
    required_files, errors = required_file_entries()
    baseline_present = tag_exists(BASELINE_TAG)
    if not baseline_present:
        errors.append(f"Missing baseline tag: {BASELINE_TAG}")

    bundle_files = [
        "release_handoff_manifest.json",
        "README.md",
        "OPERATOR_COMMANDS.md",
        "TRUTH_BOUNDARY.md",
        "CHECKSUMS.sha256",
    ]

    return {
        "app_id": APP_ID,
        "baseline_tag": BASELINE_TAG,
        "baseline_tag_present": baseline_present,
        "bundle_directory": BUNDLE_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "bundle_files": bundle_files,
        "bundle_name": "upi_app_factory_phase13j_release_handoff_bundle",
        "determinism_policy": {
            "uses_current_commit_hash": False,
            "uses_wall_clock_timestamp": False,
            "reason": "The handoff bundle must be stable across validation runs and machine handoff checks.",
        },
        "errors": errors,
        "operator_commands": OPERATOR_COMMANDS,
        "passed": not errors,
        "phase": PHASE,
        "required_release_files": required_files,
        "run_id": RUN_ID,
        "truth_boundary": TRUTH_BOUNDARY,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_bundle_documents(manifest: dict[str, Any]) -> None:
    PHASE_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    write_json(PHASE_DIR / "release_handoff_bundle_manifest.json", manifest)
    write_json(BUNDLE_DIR / "release_handoff_manifest.json", manifest)

    readme = "\n".join(
        [
            "# UPI App Factory Release Handoff Bundle",
            "",
            f"Phase: {PHASE}",
            f"Baseline tag: `{BASELINE_TAG}`",
            "",
            "## Purpose",
            "This bundle gives another local operator the minimum deterministic handoff surface needed to inspect, validate, and run the governed factory.",
            "",
            "## Operator commands",
            markdown_list(OPERATOR_COMMANDS),
            "",
            "## Truth boundary",
            TRUTH_BOUNDARY,
            "",
            "## Required release files",
            markdown_list([entry["path"] for entry in manifest["required_release_files"]]),
            "",
            "## Validation",
            "Run `python scripts/validate_phase13j_release_handoff_bundle.py` from the repository root.",
        ]
    )
    (BUNDLE_DIR / "README.md").write_text(readme + "\n", encoding="utf-8")

    commands_md = "# Operator Commands\n\n" + markdown_list(OPERATOR_COMMANDS) + "\n"
    (BUNDLE_DIR / "OPERATOR_COMMANDS.md").write_text(commands_md, encoding="utf-8")

    boundary_md = "# Truth Boundary\n\n" + TRUTH_BOUNDARY + "\n"
    (BUNDLE_DIR / "TRUTH_BOUNDARY.md").write_text(boundary_md, encoding="utf-8")

    checksum_lines = []
    for entry in manifest["required_release_files"]:
        checksum = entry.get("sha256") or "MISSING"
        checksum_lines.append(f"{checksum}  {entry['path']}")
    (BUNDLE_DIR / "CHECKSUMS.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def main() -> None:
    manifest = build_manifest()
    write_bundle_documents(manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if not manifest["passed"]:
        raise BundleError("Release handoff bundle manifest has errors.")


if __name__ == "__main__":
    main()
