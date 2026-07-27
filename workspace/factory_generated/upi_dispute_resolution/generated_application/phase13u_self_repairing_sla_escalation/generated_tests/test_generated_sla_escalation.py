from __future__ import annotations

import importlib
import pathlib
import sys

GENERATED_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(GENERATED_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_ROOT))

generated_app = importlib.import_module("phase13u_self_repairing_sla_escalation_app")
SlaEscalationRequest = generated_app.SlaEscalationRequest
validate_sla_escalation = generated_app.validate_sla_escalation


def test_generated_sla_escalation_behavior() -> None:
    on_track = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-ON-TRACK",
            elapsed_minutes=20,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert on_track.breach_detected is False
    assert on_track.escalation_status == "ON_TRACK"

    at_risk = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-RISK",
            elapsed_minutes=100,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert at_risk.breach_detected is False
    assert at_risk.escalation_status == "AT_RISK"

    breached = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-BREACH",
            elapsed_minutes=121,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert breached.breach_detected is True
    assert breached.escalation_status == "BREACHED"
