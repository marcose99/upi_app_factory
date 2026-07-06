from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase11c_upi_domain_safety_regulatory_guardrails.py"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_phase11c_upi_domain_safety_regulatory_guardrails",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase11c_upi_domain_safety_guardrails_pass() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
    assert result["prompt_files_checked"] >= 50


def test_negated_safety_terms_are_not_forbidden_positive_claims() -> None:
    validator = load_validator()
    text = (
        "Do not claim that generated artifacts are RBI certified. "
        "Never use real customer UPI ID. "
        "The app must not call live NPCI, RBI, bank, PSP, ODR, or payment rail."
    )
    assert validator._positive_forbidden_claims(text) == []


def test_positive_forbidden_claim_is_detected() -> None:
    validator = load_validator()
    text = "This generated system is RBI certified and production compliant."
    claims = validator._positive_forbidden_claims(text)
    assert claims
    assert {claim["claim"] for claim in claims} >= {"RBI certified", "production compliant"}
