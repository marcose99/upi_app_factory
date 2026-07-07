from __future__ import annotations

import importlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, cast

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
    / "phase13u_self_repairing_sla_escalation"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13u"
)


def run_script(script_name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(PROJECT_ROOT / "src"),
            str(PROJECT_ROOT / "scripts"),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / script_name)],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_phase13u_self_repairing_generation_and_behavior() -> None:
    output = run_script("run_phase13u_self_repairing_requirement_generation.py")
    assert output["passed"] is True
    assert output["phase"] == "Phase 13U"
    assert output["graph_type"] == "StateGraph"
    assert output["validation_status"] == "passed"
    assert output["repair_attempts"] == 1
    assert output["diagnosis_count"] == 1
    assert output["release_ready"] is True

    validation = run_script("validate_phase13u_self_repairing_requirement_generation.py")
    assert validation["passed"] is True
    assert validation["repair_attempts"] == 1
    assert validation["diagnosis_count"] == 1

    sys.path.insert(0, str(GENERATED_ROOT))
    module = importlib.import_module("phase13u_self_repairing_sla_escalation_app")
    request_type = getattr(module, "SlaEscalationRequest")
    validate_sla_escalation = getattr(module, "validate_sla_escalation")

    on_track = validate_sla_escalation(
        request_type(
            dispute_case_id="CASE-13U-ON-TRACK",
            elapsed_minutes=20,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert on_track.breach_detected is False
    assert on_track.escalation_status == "ON_TRACK"

    at_risk = validate_sla_escalation(
        request_type(
            dispute_case_id="CASE-13U-RISK",
            elapsed_minutes=100,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert at_risk.breach_detected is False
    assert at_risk.escalation_status == "AT_RISK"

    breached = validate_sla_escalation(
        request_type(
            dispute_case_id="CASE-13U-BREACH",
            elapsed_minutes=121,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert breached.breach_detected is True
    assert breached.escalation_status == "BREACHED"

    audit = json.loads(
        (ARTIFACT_DIR / "self_repairing_generation_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["diagnoses"][0]["category"] == "generated_behavior_mismatch"
