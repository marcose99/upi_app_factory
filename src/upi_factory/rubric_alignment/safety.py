from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from upi_factory.rubric_alignment.models import SafetyDecision
from upi_factory.rubric_alignment.utils import contains_sensitive, redact


UNSAFE_TERMS = {
    "real_payment_endpoint": ["npci production", "real bank api", "live payment", "settle money"],
    "secret_exfiltration": ["print openai_api_key", "dump secrets", "show secret", "exfiltrate"],
    "destructive_tool": ["rm -rf", "delete repository", "wipe database"],
    "approval_bypass": ["bypass approval", "ignore governance", "skip human approval"],
    "unsupported_regulatory_claim": ["rbi certified", "npci approved", "production ready"],
    "prompt_injection": ["ignore previous instructions", "reveal system prompt"],
}


def safety_flags(text: str) -> list[str]:
    lower = text.lower()
    flags = [name for name, terms in UNSAFE_TERMS.items() if any(term in lower for term in terms)]
    if contains_sensitive(text):
        flags.append("pii_or_secret")
    return sorted(set(flags))


def safety_decision(text: str, *, confidence: float = 1.0) -> tuple[SafetyDecision, list[str]]:
    flags = safety_flags(text)
    if any(flag in flags for flag in ("real_payment_endpoint", "secret_exfiltration", "destructive_tool", "approval_bypass")):
        return SafetyDecision.REFUSE, flags
    if flags or confidence < 0.65:
        return SafetyDecision.ESCALATE, flags
    return SafetyDecision.ALLOW, flags


def sanitized_log(event: str, payload: object) -> dict[str, object]:
    serializable = asdict(cast(Any, payload)) if hasattr(payload, "__dataclass_fields__") else payload
    return {"event": event, "payload": redact(str(serializable))}
