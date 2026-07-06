#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"

DOCS = ROOT / "docs" / "phase13a"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13a"
RUN_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID / "generation_runs" / RUN_ID
GENERATED_APP = ROOT / "workspace" / "factory_generated" / APP_ID / "generated_application"

REQUIRED_FILES = [
    "generation_run_manifest.json",
    "agent_execution_plan.json",
    "generated_application_target_architecture.json",
    "domain_policy_execution_inputs.json",
    "generated_application_artifact_contract.json",
    "validation_test_evaluation_plan.json",
    "post_generation_audit_and_remediation_plan.json",
    "final_portal_population_contract.json",
    "phase13a_readiness_decision.json",
    "phase13a_first_governed_generation_run_scaffold.md",
    "governed_generation_runbook.md",
]

REQUIRED_TERMS = {
    "generation_run_manifest.json": [
        "READY_TO_START_CONTROLLED_GENERATION",
        "real locally runnable UPI/payment dispute-resolution application",
        "mock/simulated only",
        "no_regulatory_compliance_claim",
    ],
    "agent_execution_plan.json": [
        "requirement_intake_agent",
        "developer_agent",
        "audit_agent",
        "portal_agent",
        "deny-by-default",
    ],
    "generated_application_target_architecture.json": [
        "FastAPI",
        "Pydantic v2",
        "SQLite",
        "structured JSON logs",
        "mock NPCI/ODR adapter",
    ],
    "domain_policy_execution_inputs.json": [
        "failed transaction lifecycle",
        "TAT/customer compensation awareness",
        "ODR complaint flow awareness",
        "PII masking",
    ],
    "generated_application_artifact_contract.json": [
        "generated_application/README.md",
        "post_generation_audit_report.md",
        "final_generation_run_report.md",
    ],
    "validation_test_evaluation_plan.json": [
        "unit tests",
        "integration tests",
        "limited local load tests",
        "HTML portal validation",
    ],
    "post_generation_audit_and_remediation_plan.json": [
        "scorecard_results.json",
        "audit_findings_register.json",
        "controlled plan-first",
    ],
    "final_portal_population_contract.json": [
        "human_validator_audit_portal.html",
        "actual generated application capability summary",
        "inline SVG/CSS animations",
    ],
    "phase13a_readiness_decision.json": [
        "READY_TO_START_CONTROLLED_GENERATION",
        "does not yet generate the final application code",
    ],
}


def _check_root(root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue
        text = path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS.get(name, []):
            if term not in text:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"missing_term:{term}"})
    return errors


def validate() -> dict[str, Any]:
    errors = _check_root(DOCS) + _check_root(WORKSPACE) + _check_root(RUN_ROOT)

    for rel in ["app", "tests", "docs", "evidence"]:
        if not (GENERATED_APP / rel).exists():
            errors.append({"path": str((GENERATED_APP / rel).relative_to(ROOT)), "error": "missing_generated_app_placeholder_dir"})

    manifest = DOCS / "generation_run_manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("decision") != "READY_TO_START_CONTROLLED_GENERATION":
            errors.append({"path": str(manifest.relative_to(ROOT)), "error": "generation_manifest_not_ready"})

    return {
        "passed": not errors,
        "phase": "Phase 13A",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "docs_files_checked": len(REQUIRED_FILES),
        "workspace_files_checked": len(REQUIRED_FILES),
        "run_files_checked": len(REQUIRED_FILES),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
