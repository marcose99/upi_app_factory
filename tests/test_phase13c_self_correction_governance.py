from __future__ import annotations
from typing import Any

import importlib.util
import json
from pathlib import Path

from factory_agent_runtime import FindingSeverity, SelfCorrectionController
from factory_agent_runtime import SelfCorrectionPolicy, ValidationFinding


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13c_self_correction_governance.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase13c_self_correction_governance",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_self_correction_controller_triages_every_finding(tmp_path: Path) -> None:
    controller = SelfCorrectionController(
        policy=SelfCorrectionPolicy(),
        ledger_root=tmp_path,
    )
    findings = [
        ValidationFinding("warn1", FindingSeverity.WARNING, "formatting", "ruff", "format"),
        ValidationFinding("err1", FindingSeverity.ERROR, "regulatory_claim", "policy", "claim"),
        ValidationFinding("err2", FindingSeverity.ERROR, "real_payment_execution", "boundary", "blocked"),
    ]
    decisions = controller.process_findings(findings)
    summary = controller.summarize(decisions)
    assert summary["total_decisions"] == 3
    assert summary["untriaged"] == 0
    assert summary["auto_remediate"] == 1
    assert summary["human_approval_required"] == 1
    assert summary["blocked"] == 1


def test_phase13c_self_correction_validator_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
