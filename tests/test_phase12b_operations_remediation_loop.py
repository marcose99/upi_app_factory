from __future__ import annotations
from typing import Any

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase12b_operations_remediation_loop.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase12b_operations_remediation_loop",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase12b_operations_remediation_loop_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_phase12b_quality_objectives_have_hard_gates() -> None:
    path = ROOT / "docs" / "phase12b" / "quality_objectives.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["minimum_scores"]["factory_governance"] == 4
    assert "no live payment rail integration" in data["hard_gates"]
    assert "no real customer data" in data["hard_gates"]


def test_phase12b_remediation_controller_plan_only(tmp_path: Path) -> None:
    report = tmp_path / "audit_report.json"
    report.write_text(
        json.dumps(
            {
                "findings": [
                    {"finding_id": "F-1", "category": "documentation_gap", "severity": "low"},
                    {"finding_id": "F-2", "category": "tool_authorization", "severity": "high"},
                ]
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_remediation_controller.py"),
            "--audit-report",
            str(report),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    plan = json.loads(completed.stdout)
    assert plan["mode"] == "plan_only"
    assert plan["planned_remediations"][0]["auto_apply_candidate"] is True
    assert plan["planned_remediations"][1]["human_approval_required"] is True
