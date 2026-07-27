from __future__ import annotations

import importlib
import sys
from pathlib import Path

GENERATED_APP_ROOT = Path(__file__).resolve().parents[1]
if str(GENERATED_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_APP_ROOT))

generated_app = importlib.import_module("phase13w_multi_capability_dispute_app")
DisputeCase = generated_app.DisputeCase
EvidenceUpload = generated_app.EvidenceUpload
process_dispute_case = generated_app.process_dispute_case


def test_valid_case_stays_standard_and_mock_bounded() -> None:
    result = process_dispute_case(
        EvidenceUpload("CASE-1", "receipt.pdf", "abc1234567890def", 2048),
        DisputeCase("CASE-1", age_hours=4, sla_hours=24, amount_paise=25000, channel="UPI"),
    )

    assert result.evidence.accepted is True
    assert result.triage.queue == "standard_dispute_ops"
    assert result.external_ecosystem_mode == "mock_only"


def test_invalid_evidence_routes_to_evidence_review() -> None:
    result = process_dispute_case(
        EvidenceUpload("CASE-2", "notes.exe", "bad", 10),
        DisputeCase("CASE-2", age_hours=2, sla_hours=24, amount_paise=25000, channel="UPI"),
    )

    assert result.evidence.accepted is False
    assert result.triage.queue == "evidence_review"
    assert result.triage.needs_escalation is True


def test_sla_breach_routes_to_sla_escalation() -> None:
    result = process_dispute_case(
        EvidenceUpload("CASE-3", "proof.png", "abc1234567890def", 1024),
        DisputeCase("CASE-3", age_hours=25, sla_hours=24, amount_paise=25000, channel="UPI"),
    )

    assert result.evidence.accepted is True
    assert result.triage.queue == "sla_escalation"
    assert "sla_breach_or_due" in result.triage.reasons
