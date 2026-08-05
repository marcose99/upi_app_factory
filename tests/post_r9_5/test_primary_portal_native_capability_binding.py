from __future__ import annotations

from pathlib import Path

from factory.native_capability_prerun.engine import PreRunConfig, build_payloads


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_authoritative_primary_portal_requirement_is_explicitly_bound_and_proven(
    tmp_path: Path,
) -> None:
    requirements = tmp_path / "requirements.md"
    requirements.write_text(
        """# Primary portal failed-debit runtime

Build and register the authoritative local failed-debit runtime with evidence collection, investigation, human review, disposition, audit verification, closure, mock-only payment boundaries, and deterministic local test proof.
""",
        encoding="utf-8",
    )

    payloads = build_payloads(
        PreRunConfig(
            requirements_document=requirements,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "native_prerun",
            factory_root=PROJECT_ROOT,
        )
    )

    report = payloads["CAPABILITY_PRE_RUN_REPORT.json"]
    item = payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]["items"][0]

    assert report["decision"] == "PROVEN_100_PERCENT_CAPABILITY"
    assert report["mandatory_gate_passed"] is True
    assert item["classification"] == "FULFILLABLE"
    assert item["proof_mode"] == "exact_text"
    assert item["proof_trace"]["explicit_requirement_binding"] is True
    assert item["proof_trace"]["implementation_evidence"]
    assert item["proof_trace"]["automated_test_evidence"]
    assert item["proof_trace"]["requirement_to_code_and_test_complete"] is True
    assert [
        capability["id"] for capability in item["matched_capabilities"]
    ] == ["CAP-PORTAL-AUTHORITATIVE-FAILED-DEBIT-RUNTIME"]
