from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_FILES = [
    "factory_governance/phase2/upi_dispute_requirements.v1.json",
    "factory_governance/phase2/mock_external_system_contracts.v1.json",
    "docs/phase_2/requirements_and_mock_ecosystem.md",
    "evidence/releases/phase_2_requirements_mock_ecosystem.md",
    "factory_governance/phase3/architecture_design_contract.v1.json",
    "docs/phase_3/architecture_options.md",
    "docs/phase_3/architecture_decision.md",
    "docs/phase_3/module_designs.md",
    "docs/phase_3/diagrams.md",
    "docs/phase_3/work_breakdown_structure.md",
    "app/disputes/models.py",
    "app/disputes/service.py",
    "app/disputes/router.py",
    "adapters/mock_upi_switch.py",
    "adapters/mock_core_banking.py",
    "adapters/mock_customer_notification.py",
    "adapters/mock_dispute_evidence_store.py",
    "docs/demo/demo_storyline.md",
    "docs/demo/reviewer_walkthrough.md",
    "docs/demo/api_test_commands.md",
    "scripts/run_phase5_smoke_tests.sh",
    "evidence/releases/phase_5_final_validation_pack.md",
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
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {relative_path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"JSON root must be object in {relative_path}")
        return {}
    return data


def require_labels(text: str, relative_path: str, errors: list[str]) -> None:
    for label in sorted(REQUIRED_LABELS):
        if label not in text:
            errors.append(f"required label {label} missing in {relative_path}")


def validate() -> ValidationResult:
    errors: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).is_file():
            errors.append(f"required file missing: {relative_path}")

    requirements = read_json(
        "factory_governance/phase2/upi_dispute_requirements.v1.json",
        errors,
    )
    if requirements.get("real_payment_calls_allowed") is not False:
        errors.append("Phase 2 requirements must forbid real payment calls")
    for label in sorted(REQUIRED_LABELS):
        if label not in set(requirements.get("evidence_labels_required", [])):
            errors.append(f"Phase 2 missing label: {label}")

    ecosystem = read_json(
        "factory_governance/phase2/mock_external_system_contracts.v1.json",
        errors,
    )
    systems = ecosystem.get("systems", [])
    if not isinstance(systems, list) or len(systems) < 4:
        errors.append("Phase 2 mock ecosystem must define at least four systems")
    else:
        for system in systems:
            if not isinstance(system, dict):
                errors.append("Mock ecosystem entry must be object")
                continue
            if system.get("boundary") != "MOCK_BOUNDARY":
                errors.append("Every external system must be MOCK_BOUNDARY")
            if system.get("data_label") != "SYNTHETIC_DATA":
                errors.append("Every external system must use SYNTHETIC_DATA")
            if system.get("real_integration_allowed") is not False:
                errors.append("Every external system must forbid real integration")

    architecture = read_json(
        "factory_governance/phase3/architecture_design_contract.v1.json",
        errors,
    )
    if architecture.get("selected_architecture") != (
        "lightweight_fastapi_modular_mock_adapters"
    ):
        errors.append("Phase 3 selected architecture is incorrect")
    if architecture.get("model_provider") != "OpenAI":
        errors.append("Phase 3 model provider must be OpenAI")
    if architecture.get("real_payment_calls_allowed") is not False:
        errors.append("Phase 3 must forbid real payment calls")

    main_text = read_text("app/main.py", errors)
    if "from app.disputes.router import router as disputes_router" not in main_text:
        errors.append("app.main must import disputes_router")
    if "app.include_router(disputes_router)" not in main_text:
        errors.append("app.main must include disputes_router")

    router_text = read_text("app/disputes/router.py", errors)
    for route in [
        "/mock-failed-transactions",
        "/cases/from-failed-transaction",
        "/cases/{case_id}/actions",
    ]:
        if route not in router_text:
            errors.append(f"route missing from router: {route}")

    models_text = read_text("app/disputes/models.py", errors)
    require_labels(models_text, "app/disputes/models.py", errors)

    for doc_path in [
        "docs/phase_2/requirements_and_mock_ecosystem.md",
        "evidence/releases/phase_2_requirements_mock_ecosystem.md",
        "docs/phase_3/architecture_options.md",
        "docs/phase_3/architecture_decision.md",
        "docs/phase_3/module_designs.md",
        "docs/phase_3/diagrams.md",
        "docs/phase_3/work_breakdown_structure.md",
        "docs/demo/demo_storyline.md",
        "docs/demo/reviewer_walkthrough.md",
        "docs/demo/api_test_commands.md",
        "evidence/releases/phase_5_final_validation_pack.md",
    ]:
        require_labels(read_text(doc_path, errors), doc_path, errors)

    smoke = PROJECT_ROOT / "scripts/run_phase5_smoke_tests.sh"
    if smoke.exists() and not smoke.stat().st_mode & 0o111:
        errors.append("scripts/run_phase5_smoke_tests.sh must be executable")

    return ValidationResult(passed=not errors, errors=errors)


def main() -> int:
    result = validate()
    print(json.dumps({"passed": result.passed, "errors": result.errors}, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
