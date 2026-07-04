from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_BASELINE_BASENAMES = [
    "00_SYSTEM_PROMPT.md",
    "01_PROJECT_CHARTER_TEMPLATE.md",
    "02_FACTORY_OPERATING_MANUAL.md",
    "03_AGENT_ROLE_PROMPTS.md",
    "05_POLICY_REGISTRY.yaml",
    "06_VALIDATION_GATES.yaml",
    "12_DEBUGGING_PLAYBOOK.md",
    "13_RELEASE_READINESS_CHECKLIST.md",
    "14_SECURITY_AND_RED_TEAM_PLAYBOOK.md",
]

REQUIRED_EVIDENCE_LABELS = [
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: list[str]


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing file: {path.relative_to(PROJECT_ROOT)}")
        return {}

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON: {path}: {exc}")
        return {}

    if not isinstance(value, dict):
        errors.append(f"JSON root must be object: {path}")
        return {}

    return value


def validate() -> ValidationResult:
    errors: list[str] = []

    manifest_path = (
        PROJECT_ROOT / "factory_governance/baseline_provenance_manifest.json"
    )
    manifest = read_json(manifest_path, errors)

    if manifest.get("provenance_status") != "PROVEN_AND_PRESERVED":
        errors.append("provenance_status must be PROVEN_AND_PRESERVED")

    source_zip = manifest.get("source_zip", {})
    if not isinstance(source_zip, dict):
        errors.append("source_zip must be an object")
    else:
        sha256_value = source_zip.get("sha256")
        if not isinstance(sha256_value, str) or len(sha256_value) != 64:
            errors.append("source_zip.sha256 must be a 64-character hash")

    preservation = manifest.get("baseline_preservation", {})
    preserved_path = ""

    if not isinstance(preservation, dict):
        errors.append("baseline_preservation must be an object")
    else:
        preserved_path_value = preservation.get(
            "preserved_under_version_control_path"
        )
        preserved_path = (
            preserved_path_value
            if isinstance(preserved_path_value, str)
            else ""
        )

        if not preserved_path:
            errors.append("preserved path is missing")

        count = preservation.get("extracted_file_count")
        if not isinstance(count, int) or count <= 0:
            errors.append("extracted_file_count must be positive")

        missing = preservation.get("missing_required_baseline_files")
        if missing not in ([], None):
            errors.append("missing_required_baseline_files must be empty")

    baseline_root = PROJECT_ROOT / preserved_path if preserved_path else PROJECT_ROOT
    if preserved_path and not baseline_root.is_dir():
        errors.append(f"preserved baseline directory missing: {preserved_path}")

    extracted_basenames = {
        path.name for path in baseline_root.rglob("*") if path.is_file()
    }

    for basename in REQUIRED_BASELINE_BASENAMES:
        if basename not in extracted_basenames:
            errors.append(f"required preserved baseline file missing: {basename}")

    docs = [
        PROJECT_ROOT / "docs/phase_6/baseline_provenance_audit.md",
        PROJECT_ROOT
        / "evidence/releases/factory_governance_baseline_provenance.md",
    ]

    for path in docs:
        if not path.is_file():
            errors.append(f"missing file: {path.relative_to(PROJECT_ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for label in REQUIRED_EVIDENCE_LABELS:
            if label not in text:
                errors.append(
                    f"required label {label} missing in "
                    f"{path.relative_to(PROJECT_ROOT)}"
                )

    return ValidationResult(passed=not errors, errors=errors)


def main() -> int:
    result = validate()
    print(json.dumps({"passed": result.passed, "errors": result.errors}, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
