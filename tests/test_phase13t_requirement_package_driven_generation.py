from __future__ import annotations

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
    / "phase13t_requirement_driven_sla_detection"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13t"
)


def run_phase13t_generation() -> dict[str, Any]:
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
        [
            sys.executable,
            str(
                PROJECT_ROOT
                / "scripts"
                / "run_phase13t_requirement_package_driven_generation.py"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_phase13t_requirement_driven_generation_outputs_and_behavior() -> None:
    output = run_phase13t_generation()
    assert output["passed"] is True
    assert output["phase"] == "Phase 13T"
    assert output["graph_type"] == "StateGraph"
    assert output["requirement_source"] == "external_or_default_json_package"

    sys.path.insert(0, str(GENERATED_ROOT))
    from phase13t_requirement_driven_sla_detection_app import (
        SlaAssessmentRequest,
        assess_sla_status,
    )

    within_request = SlaAssessmentRequest(
        dispute_case_id="CASE-13T-001",
        transaction_id="TXN-13T-000001",
        received_at_utc="2026-07-07T00:00:00+00:00",
        now_utc="2026-07-07T02:00:00+00:00",
        sla_hours=24,
        priority="normal",
    )
    within = assess_sla_status(within_request)
    assert within.breached is False
    assert within.sla_status == "WITHIN_SLA"
    assert within.remaining_minutes == 1320

    breached_request = within_request.model_copy(
        update={"now_utc": "2026-07-08T06:30:00+00:00", "priority": "regulatory"}
    )
    breached = assess_sla_status(breached_request)
    assert breached.breached is True
    assert breached.escalation_required is True
    assert breached.sla_status == "ESCALATE_NOW"
    assert "SLA_BREACHED" in breached.risk_flags
    assert "ESCALATION_REQUIRED" in breached.risk_flags

    traceability = json.loads(
        (ARTIFACT_DIR / "requirement_traceability_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    mapping = traceability["mappings"][0]
    assert mapping["requirement_id"] == "REQ-13T-SLA-BREACH-DETECTION"
    assert "contracts.py" in " ".join(mapping["code_files"])
    assert "service.py" in " ".join(mapping["code_files"])
