from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from upi_factory.phase11c_requirement_intake_capability_classification import (
    GENERATION_MODE,
    REQUIRED_ARTIFACTS,
    classify_payment_capabilities,
    generate_phase11c_artifacts,
    validate_phase11c_artifacts,
    validate_requirement_document,
)


VALID_REQUIREMENT = """---
requirement_id: REQ-UPI-DISPUTE-001
app_id: upi_dispute_resolution
domain: payments
generation_mode: real_local_primary_payment_application_with_mock_ecosystem
primary_application_real: true
external_ecosystem_mock_only: true
synthetic_data_only: true
external_payment_connectivity_allowed: false
real_payment_processing_allowed: false
production_claims_allowed: false
---

BR-001:
Build a real local UPI dispute resolution application.

FR-001:
Create a dispute case.

NFR-001:
Use local-first lightweight implementation.

GR-001:
External ecosystem applications must be simulated.

MOCK-001:
Use a simulated transaction registry.

AC-001:
A valid synthetic dispute can be created.
"""


def _write_requirement(tmp_path: Path, text: str = VALID_REQUIREMENT) -> Path:
    path = tmp_path / "requirement.md"
    path.write_text(text, encoding="utf-8")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def test_requirement_document_validation_accepts_valid_boundary(
    tmp_path: Path,
) -> None:
    requirement_doc = _write_requirement(tmp_path)

    report = validate_requirement_document(requirement_doc)

    assert report["passed"] is True
    assert report["errors"] == []


def test_requirement_document_validation_rejects_unsafe_claim(
    tmp_path: Path,
) -> None:
    requirement_doc = _write_requirement(
        tmp_path,
        VALID_REQUIREMENT + "\nThis is production ready.\n",
    )

    report = validate_requirement_document(requirement_doc)

    assert report["passed"] is False
    assert any("production ready" in error for error in report["errors"])


def test_payment_capability_classifier_detects_upi_dispute() -> None:
    classification = classify_payment_capabilities(VALID_REQUIREMENT)

    assert classification["capability_count"] >= 1
    primary = classification["primary_capability"]
    assert isinstance(primary, dict)
    assert primary["capability_id"] == "upi_dispute_resolution"


def test_phase11c_generation_creates_required_artifacts(tmp_path: Path) -> None:
    requirement_doc = _write_requirement(tmp_path)
    output_dir = tmp_path / "out"

    generated = generate_phase11c_artifacts(output_dir, requirement_doc)
    generated_names = {path.name for path in generated}

    assert set(REQUIRED_ARTIFACTS) == generated_names
    for artifact_name in REQUIRED_ARTIFACTS:
        assert (output_dir / artifact_name).exists()


def test_phase11c_generation_contract_preserves_boundary(tmp_path: Path) -> None:
    requirement_doc = _write_requirement(tmp_path)
    output_dir = tmp_path / "out"

    generate_phase11c_artifacts(output_dir, requirement_doc)
    contract = _load_json(output_dir / "generation_contract.json")

    assert contract["generation_mode"] == GENERATION_MODE
    assert contract["primary_application_real"] is True
    assert contract["external_ecosystem_mock_only"] is True
    assert contract["synthetic_data_only"] is True
    assert contract["external_payment_connectivity_allowed"] is False
    assert contract["real_payment_processing_allowed"] is False
    assert contract["production_claims_allowed"] is False


def test_phase11c_validation_passes_for_generated_artifacts(
    tmp_path: Path,
) -> None:
    requirement_doc = _write_requirement(tmp_path)
    output_dir = tmp_path / "out"

    generate_phase11c_artifacts(output_dir, requirement_doc)
    report = validate_phase11c_artifacts(output_dir)

    assert report["passed"] is True
    assert report["errors"] == []



def test_phase11c_generation_contract_requires_llm_expense_tracking(
    tmp_path: Path,
) -> None:
    requirement_doc = _write_requirement(tmp_path)
    output_dir = tmp_path / "out"

    generate_phase11c_artifacts(output_dir, requirement_doc)
    contract = _load_json(output_dir / "generation_contract.json")

    assert contract["llm_expense_tracking_required"] is True

    expense_tracking = contract["llm_expense_tracking"]
    assert expense_tracking["pricing_config_required"] is True
    assert expense_tracking["per_call_ledger_required"] is True
    assert expense_tracking["final_summary_required"] is True
    assert expense_tracking["no_llm_calls_after_final_summary"] is True
    assert "calculated_cost" in expense_tracking["per_call_required_fields"]
    assert "llm_expense_summary.json" in expense_tracking["final_summary_artifacts"]


def test_phase11c_generates_llm_expense_tracking_policy(
    tmp_path: Path,
) -> None:
    requirement_doc = _write_requirement(tmp_path)
    output_dir = tmp_path / "out"

    generate_phase11c_artifacts(output_dir, requirement_doc)

    policy_path = output_dir / "llm_expense_tracking_policy.md"
    assert policy_path.exists()
    policy_text = policy_path.read_text(encoding="utf-8")
    assert "per-call ledger" in policy_text
    assert "No additional LLM calls" in policy_text
