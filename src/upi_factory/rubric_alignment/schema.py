from __future__ import annotations

from typing import Any

from upi_factory.rubric_alignment.models import Phase66Error, RequirementAnalysis


ExpectedType = type[Any] | tuple[type[Any], ...]


REQUIRED_FIELDS: dict[str, ExpectedType] = {
    "case_id": str,
    "summary": str,
    "capabilities": list,
    "ambiguities": list,
    "unsupported_claims": list,
    "safety_flags": list,
    "confidence": (int, float),
    "human_escalation": bool,
    "citations": list,
}


def validate_analysis(payload: dict[str, Any]) -> RequirementAnalysis:
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in payload:
            raise Phase66Error(f"schema rejection: missing {field}")
        if not isinstance(payload[field], expected_type):
            raise Phase66Error(f"schema rejection: invalid {field}")
    confidence = float(payload["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        raise Phase66Error("schema rejection: confidence outside 0..1")
    for field in ("capabilities", "ambiguities", "unsupported_claims", "safety_flags", "citations"):
        if not all(isinstance(item, str) for item in payload[field]):
            raise Phase66Error(f"schema rejection: {field} must contain strings")
    return RequirementAnalysis(
        case_id=payload["case_id"],
        summary=payload["summary"],
        capabilities=list(payload["capabilities"]),
        ambiguities=list(payload["ambiguities"]),
        unsupported_claims=list(payload["unsupported_claims"]),
        safety_flags=list(payload["safety_flags"]),
        confidence=confidence,
        human_escalation=bool(payload["human_escalation"]),
        citations=list(payload["citations"]),
    )
