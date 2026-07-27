from __future__ import annotations

import importlib
import pathlib
import sys

GENERATED_APP_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(GENERATED_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_APP_ROOT))

generated_app = importlib.import_module("phase13v_policy_governed_dispute_triage_app")
DisputeTriageRequest = generated_app.DisputeTriageRequest
triage_dispute = generated_app.triage_dispute


def test_regulatory_complaint_requires_critical_escalation() -> None:
    decision = triage_dispute(
        DisputeTriageRequest(
            dispute_id="UPI-DISP-13V-001",
            age_hours=2,
            amount_minor=2500,
            customer_segment="retail",
            regulatory_complaint=True,
            fraud_signal_score=10,
        )
    )
    assert decision.action == "ESCALATE"
    assert decision.priority == "CRITICAL"
    assert "POL-13V-POLICY-GOVERNED-GENERATION" in decision.policy_ids
