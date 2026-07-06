#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
GENERATED_APP = ROOT / "workspace" / "factory_generated" / APP_ID / "generated_application"

REQUIRED_APP_FILES = [
    "README.md",
    "app/upi_dispute_app/__init__.py",
    "app/upi_dispute_app/models.py",
    "app/upi_dispute_app/pii.py",
    "app/upi_dispute_app/audit.py",
    "app/upi_dispute_app/repository.py",
    "app/upi_dispute_app/workflow.py",
    "app/upi_dispute_app/mock_ecosystem.py",
    "app/upi_dispute_app/main.py",
    "tests/test_api.py",
    "tests/test_workflow.py",
    "tests/test_pii.py",
    "docs/architecture.md",
    "docs/hld.md",
    "docs/lld.md",
    "docs/api_contract.md",
    "docs/data_model.md",
    "docs/workflow_state_machine.md",
    "docs/security_design.md",
    "docs/observability_design.md",
    "docs/test_strategy.md",
    "evidence/generation_summary.json",
]

REQUIRED_TERMS = {
    "README.md": ["locally runnable", "mock/simulated", "does not claim production readiness"],
    "app/upi_dispute_app/main.py": ["FastAPI", "mock-ecosystem-check", "BOUNDARY_NOTICE"],
    "app/upi_dispute_app/mock_ecosystem.py": ["MockBankAdapter", "MockPspAdapter", "MockOdrAdapter"],
    "app/upi_dispute_app/workflow.py": ["ESCALATED_TO_ODR", "REFUND_INITIATED"],
    "app/upi_dispute_app/pii.py": ["mask_upi_id", "sensitive data"],
    "docs/architecture.md": ["local FastAPI service", "mock/simulated only"],
    "docs/security_design.md": ["no live external integrations", "no production secrets"],
    "evidence/generation_summary.json": ["no_live_integrations", "no_real_customer_data"],
}


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    for rel in REQUIRED_APP_FILES:
        path = GENERATED_APP / rel
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue
        text = path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS.get(rel, []):
            if term not in text:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"missing_term:{term}"})

    summary = GENERATED_APP / "evidence" / "generation_summary.json"
    if summary.exists():
        data = json.loads(summary.read_text(encoding="utf-8"))
        if data.get("no_live_integrations") is not True:
            errors.append({"path": str(summary.relative_to(ROOT)), "error": "live_boundary_not_true"})
        if data.get("no_real_customer_data") is not True:
            errors.append({"path": str(summary.relative_to(ROOT)), "error": "real_data_boundary_not_true"})

    return {
        "passed": not errors,
        "phase": "Phase 13B",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "required_files_checked": len(REQUIRED_APP_FILES),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
