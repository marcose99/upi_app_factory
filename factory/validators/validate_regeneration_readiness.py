from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_EVIDENCE_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_FILES = [
    "factory/generators/mock_dispute_app_generator.py",
    "factory/templates/mock_dispute_app/template_manifest.v1.json",
    "factory/templates/mock_dispute_app/app/disputes/__init__.py",
    "factory/templates/mock_dispute_app/app/disputes/models.py",
    "factory/templates/mock_dispute_app/app/disputes/service.py",
    "factory/templates/mock_dispute_app/app/disputes/router.py",
    "factory/templates/mock_dispute_app/adapters/mock_upi_switch.py",
    "factory/templates/mock_dispute_app/adapters/mock_core_banking.py",
    "factory/templates/mock_dispute_app/adapters/mock_customer_notification.py",
    "factory/templates/mock_dispute_app/adapters/mock_dispute_evidence_store.py",
    "scripts/regenerate_mock_dispute_app.sh",
    "docs/phase_6/regeneration_automation.md",
    "evidence/releases/phase_6_regeneration_automation.md",
]


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: list[str]


def read_text(relative_path: str, errors: list[str]) -> str:
    try:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"required file missing: {relative_path}")
        return ""


def read_json(relative_path: str, errors: list[str]) -> dict[str, Any]:
    text = read_text(relative_path, errors)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {relative_path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON root must be object in {relative_path}")
        return {}
    return value


def require_labels(text: str, relative_path: str, errors: list[str]) -> None:
    for label in sorted(REQUIRED_EVIDENCE_LABELS):
        if label not in text:
            errors.append(f"required evidence label {label} missing in {relative_path}")


def validate() -> ValidationResult:
    errors: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).is_file():
            errors.append(f"required file missing: {relative_path}")

    manifest = read_json(
        "factory/templates/mock_dispute_app/template_manifest.v1.json",
        errors,
    )

    if manifest.get("regeneration_mode") != "deterministic_template_regeneration":
        errors.append("template manifest must use deterministic_template_regeneration")

    labels = set(manifest.get("evidence_labels_required", []))
    for label in sorted(REQUIRED_EVIDENCE_LABELS - labels):
        errors.append(f"template manifest missing evidence label {label}")

    template_files = manifest.get("template_files", [])
    if not isinstance(template_files, list) or len(template_files) < 8:
        errors.append("template manifest must include at least 8 template files")

    generator_text = read_text(
        "factory/generators/mock_dispute_app_generator.py",
        errors,
    )
    for phrase in [
        "validate_governance_inputs",
        "real_payment_calls_allowed",
        "MOCK_BOUNDARY",
        "SYNTHETIC_DATA",
    ]:
        if phrase not in generator_text:
            errors.append(f"generator missing required phrase: {phrase}")

    script_path = PROJECT_ROOT / "scripts/regenerate_mock_dispute_app.sh"
    if script_path.exists() and not script_path.stat().st_mode & 0o111:
        errors.append("scripts/regenerate_mock_dispute_app.sh must be executable")

    for text_path in [
        "docs/phase_6/regeneration_automation.md",
        "evidence/releases/phase_6_regeneration_automation.md",
    ]:
        require_labels(read_text(text_path, errors), text_path, errors)

    return ValidationResult(passed=not errors, errors=errors)


def main() -> int:
    result = validate()
    print(json.dumps({"passed": result.passed, "errors": result.errors}, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
