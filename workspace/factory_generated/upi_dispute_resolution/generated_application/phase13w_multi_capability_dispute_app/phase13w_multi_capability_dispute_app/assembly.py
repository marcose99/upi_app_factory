"""Generated multi-capability assembly service."""
from __future__ import annotations

from .contracts import DisputeCase, EvidenceUpload, MultiCapabilityResult
from .evidence_validation import validate_evidence
from .sla_triage import decide_triage


def process_dispute_case(upload: EvidenceUpload, case: DisputeCase) -> MultiCapabilityResult:
    evidence_result = validate_evidence(upload)
    triage_decision = decide_triage(case, evidence_result)
    return MultiCapabilityResult(
        case_id=case.case_id,
        evidence=evidence_result,
        triage=triage_decision,
        external_ecosystem_mode="mock_only",
    )
