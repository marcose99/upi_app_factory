#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from factory_agent_runtime import FindingSeverity, SelfCorrectionController
from factory_agent_runtime import SelfCorrectionPolicy, ValidationFinding


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
RUN_ROOT = WORKSPACE_ROOT / "generation_runs" / RUN_ID
SELF_CORRECTION_ROOT = RUN_ROOT / "self_correction"
LEDGER_ROOT = RUN_ROOT / "agent_runtime_ledgers"


def sample_findings() -> list[ValidationFinding]:
    return [
        ValidationFinding(
            finding_id="warn_formatting_001",
            severity=FindingSeverity.WARNING,
            category="formatting",
            source="ruff",
            summary="Formatting warning should be auto-remediated.",
        ),
        ValidationFinding(
            finding_id="err_import_path_001",
            severity=FindingSeverity.ERROR,
            category="import_path",
            source="pytest",
            summary="Import path error should be auto-remediated.",
        ),
        ValidationFinding(
            finding_id="warn_portal_population_001",
            severity=FindingSeverity.WARNING,
            category="portal_population",
            source="portal_validator",
            summary="Portal population warning should be auto-remediated.",
        ),
        ValidationFinding(
            finding_id="err_regulatory_claim_001",
            severity=FindingSeverity.ERROR,
            category="regulatory_claim",
            source="forbidden_claim_validator",
            summary="Regulatory claim wording requires human approval.",
        ),
        ValidationFinding(
            finding_id="warn_dependency_install_001",
            severity=FindingSeverity.WARNING,
            category="dependency_install",
            source="runtime_adapter",
            summary="Dependency installation requires human approval.",
        ),
        ValidationFinding(
            finding_id="err_real_payment_001",
            severity=FindingSeverity.ERROR,
            category="real_payment_execution",
            source="mock_boundary_validator",
            summary="Real payment execution is blocked.",
        ),
    ]


def main() -> int:
    SELF_CORRECTION_ROOT.mkdir(parents=True, exist_ok=True)
    controller = SelfCorrectionController(
        policy=SelfCorrectionPolicy(),
        ledger_root=LEDGER_ROOT,
    )
    findings = sample_findings()
    decisions = controller.process_findings(findings)
    summary = controller.summarize(decisions)
    report = {
        "phase": "Phase 13C",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "coverage_rule": "every finding receives a governed decision",
        "summary": summary,
        "decisions": [decision.to_jsonable() for decision in decisions],
    }
    report_path = SELF_CORRECTION_ROOT / "self_correction_decisions.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if summary["untriaged"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
