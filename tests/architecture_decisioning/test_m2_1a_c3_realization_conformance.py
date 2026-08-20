from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any

import pytest

from factory.application_engineering.architecture_conformance import (
    validate_architecture_conformance,
    verify_architecture_conformance_report,
)
from factory.application_engineering.architecture_realization import (
    get_architecture_adapter,
    load_architecture_realization_contract,
)
from factory.application_engineering.deep_composer import (
    DeepApplicationComposer,
    DeepComposerError,
    GOLDEN_APP_ID,
    canonical_json,
    sha256_text,
)
from factory.application_engineering.requirements_compiler import compile_requirements
from factory.architecture_decisioning import (
    ArchitectureDecisionError,
    ArchitectureHumanGate,
    adjudicate_architecture_reviews,
    build_architecture_review_packet,
    build_evolution_contract,
    build_review_requests,
    build_reviewed_architecture_package,
    canonical_sha256,
    compile_driver_ir,
    decide_architecture,
    freeze_review_set,
    freeze_reviewed_architecture,
    load_architecture_contract,
    load_architecture_review_contract,
    verify_reviewed_architecture_freeze,
    verify_reviewed_architecture_package,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/phase53/failed_debit_requirements.md"
ARCH_CONTRACT_PATH = ROOT / "config/architecture_decisioning/kernel_contract.v2.json"
REVIEW_CONTRACT_PATH = ROOT / "config/architecture_decisioning/review_contract.v2.json"
REALIZATION_CONTRACT_PATH = ROOT / "config/architecture_decisioning/realization_contract.v1.json"

EXECUTABLE_PATTERNS = (
    "MODULAR_MONOLITH_HEXAGONAL",
    "WORKFLOW_CENTRIC_MODULAR_MONOLITH",
    "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX",
)


def requirements_ir() -> dict[str, Any]:
    return compile_requirements([FIXTURE], ROOT)


def requirements_hash() -> str:
    return sha256_text(canonical_json(requirements_ir()))


def architecture_contract() -> dict[str, Any]:
    return load_architecture_contract(ARCH_CONTRACT_PATH)


def review_contract() -> dict[str, Any]:
    return load_architecture_review_contract(REVIEW_CONTRACT_PATH)


def realization_contract() -> dict[str, Any]:
    return load_architecture_realization_contract(REALIZATION_CONTRACT_PATH)


def observations() -> list[dict[str, Any]]:
    return [
        {
            "driver_id": "transaction_consistency",
            "source_class": "EXPLICIT_REQUIREMENT",
            "value": "strong_single_case_consistency",
            "confidence": 1.0,
            "hard_constraint": True,
            "evidence": ["REQ-TXN-001"],
        },
        {
            "driver_id": "auditability",
            "source_class": "EXPLICIT_REQUIREMENT",
            "value": "append_only_evidence_required",
            "confidence": 1.0,
            "hard_constraint": True,
            "evidence": ["REQ-EVD-001"],
        },
        {
            "driver_id": "model_provider_replaceability",
            "source_class": "DERIVED_STRONG",
            "value": "ports_and_adapters",
            "confidence": 0.9,
            "hard_constraint": False,
            "evidence": ["ARCH-DUR-001"],
        },
    ]


def local_context() -> dict[str, Any]:
    return {
        "local_only": True,
        "mock_only": True,
        "real_payment_calls": "disabled",
        "allow_external_infrastructure": False,
        "acceptance_bar_delta": 0.0,
        "material_trust_boundary_change": False,
    }


def forced_overrides(pattern_id: str) -> dict[str, dict[str, int]]:
    dimensions = architecture_contract()["score_dimensions"]
    result: dict[str, dict[str, int]] = {}
    for pattern in architecture_contract()["patterns"]:
        candidate_id = str(pattern["pattern_id"])
        result[candidate_id] = {
            dimension: (100 if candidate_id == pattern_id else 35)
            for dimension in dimensions
        }
    return result


def make_report(
    request: dict[str, Any],
    recommendation: str,
) -> dict[str, Any]:
    candidates = [
        str(row["pattern_id"])
        for row in request["architecture_packet"]["scores"]
    ]
    report: dict[str, Any] = {
        "schema_version": review_contract()["report_schema_version"],
        "lane_id": request["lane_id"],
        "request_digest": request["request_digest"],
        "architecture_packet_digest": request["architecture_packet_digest"],
        "prior_reports_visible": False,
        "recommended_candidate_id": recommendation,
        "candidate_assessments": [
            {
                "candidate_id": candidate,
                "score_adjustments": {},
                "summary": f"independent evidence-bound assessment of {candidate}",
            }
            for candidate in candidates
        ],
        "findings": [],
        "confidence": 0.95,
    }
    report["report_digest"] = canonical_sha256(report)
    return report


def reviewed_package(pattern_id: str) -> dict[str, Any]:
    arch = architecture_contract()
    review = review_contract()
    realization = realization_contract()
    req_hash = requirements_hash()
    driver_ir = compile_driver_ir(req_hash, observations(), arch)
    decision = decide_architecture(
        requirements_sha256=req_hash,
        observations=observations(),
        contract=arch,
        context=local_context(),
        weights=None,
        dimension_overrides=forced_overrides(pattern_id),
    )
    assert decision["decision_status"] == "SELECTED"
    assert decision["selected_candidate_id"] == pattern_id
    evolution = build_evolution_contract(decision, driver_ir, arch)
    sensitivity: dict[str, Any] = {
        "base_winner": pattern_id,
        "base_scores": decision["scores"],
        "scenarios": [],
        "winner_stability": "STABLE",
    }
    sensitivity["digest"] = canonical_sha256(sensitivity)
    packet = build_architecture_review_packet(
        decision,
        sensitivity,
        arch,
        review,
        driver_ir=driver_ir,
        evolution_contract=evolution,
        evidence_catalog=[
            {
                "evidence_id": "C3-ARCH-EVIDENCE-001",
                "sha256": "e" * 64,
                "purpose": "reviewed architecture realization proof",
            }
        ],
    )
    requests = build_review_requests(packet, review)
    reports = [make_report(request, pattern_id) for request in requests]
    review_set = freeze_review_set(reports, packet, review, arch)
    adjudication = adjudicate_architecture_reviews(
        packet, review_set, review, arch
    )
    assert adjudication["status"] == "SELECTED_REVIEWED"
    assert adjudication["selected_candidate_id"] == pattern_id
    return build_reviewed_architecture_package(
        upstream_decision=decision,
        driver_ir=driver_ir,
        architecture_contract=arch,
        review_contract=review,
        architecture_packet=packet,
        review_set=review_set,
        adjudication=adjudication,
        realization_contract=realization,
    )


def workspace(name: str) -> Path:
    path = ROOT / "workspace/deep_engineering_campaign/c3_test_runs" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def generated_root(output: Path) -> Path:
    return output / GOLDEN_APP_ID


def test_realization_contract_is_digest_bound_and_supports_exactly_three_automatic_patterns() -> None:
    contract = realization_contract()
    assert contract["schema_version"] == "upi-app-factory.architecture-realization-contract.v1"
    assert contract["minimum_review_confidence_level"] == "MEDIUM"
    assert contract["no_silent_fallback"] is True
    assert [row["pattern_id"] for row in contract["patterns"]] == list(EXECUTABLE_PATTERNS)
    assert set(contract["unsupported_patterns"]) == {
        "CQRS_EVENT_ORIENTED",
        "SERVICE_ORIENTED_DISTRIBUTED",
    }
    assert contract["contract_digest"] == canonical_sha256(
        {key: value for key, value in contract.items() if key != "contract_digest"}
    )


def test_reviewed_freeze_and_package_are_transitively_digest_bound() -> None:
    package = reviewed_package("MODULAR_MONOLITH_HEXAGONAL")
    freeze = package["reviewed_freeze"]
    assert verify_reviewed_architecture_freeze(
        freeze=freeze,
        upstream_decision=package["upstream_decision"],
        driver_ir=package["driver_ir"],
        architecture_contract=package["architecture_contract"],
        review_contract=package["review_contract"],
        architecture_packet=package["architecture_packet"],
        review_set=package["review_set"],
        adjudication=package["adjudication"],
        realization_contract=package["realization_contract"],
    )
    assert verify_reviewed_architecture_package(package)
    assert freeze["selected_candidate_id"] == "MODULAR_MONOLITH_HEXAGONAL"
    assert freeze["adapter_id"] == "hexagonal_modular_monolith_v1"
    assert freeze["requirements_sha256"] == requirements_hash()
    assert freeze["freeze_digest"] == canonical_sha256(
        {key: value for key, value in freeze.items() if key != "freeze_digest"}
    )

    tampered = deepcopy(package)
    tampered["adjudication"]["selected_candidate_id"] = "WORKFLOW_CENTRIC_MODULAR_MONOLITH"
    assert verify_reviewed_architecture_package(tampered) is False


def test_reviewed_freeze_rejects_non_selected_reviewed_status_and_low_confidence() -> None:
    package = reviewed_package("MODULAR_MONOLITH_HEXAGONAL")
    bad_adjudication = deepcopy(package["adjudication"])
    bad_adjudication["status"] = "PROTOTYPE_REQUIRED"
    bad_adjudication["selected_candidate_id"] = None
    bad_adjudication["adjudication_digest"] = canonical_sha256(
        {
            key: value
            for key, value in bad_adjudication.items()
            if key != "adjudication_digest"
        }
    )
    with pytest.raises(ArchitectureDecisionError):
        freeze_reviewed_architecture(
            upstream_decision=package["upstream_decision"],
            driver_ir=package["driver_ir"],
            architecture_contract=package["architecture_contract"],
            review_contract=package["review_contract"],
            architecture_packet=package["architecture_packet"],
            review_set=package["review_set"],
            adjudication=bad_adjudication,
            realization_contract=package["realization_contract"],
        )

    low = deepcopy(package["adjudication"])
    assert isinstance(low["confidence"], dict)
    low["confidence"]["level"] = "LOW"
    low["confidence"]["score"] = 0.4
    low["confidence"]["digest"] = canonical_sha256(
        {
            key: value
            for key, value in low["confidence"].items()
            if key != "digest"
        }
    )
    low["adjudication_digest"] = canonical_sha256(
        {key: value for key, value in low.items() if key != "adjudication_digest"}
    )
    with pytest.raises(ArchitectureHumanGate):
        freeze_reviewed_architecture(
            upstream_decision=package["upstream_decision"],
            driver_ir=package["driver_ir"],
            architecture_contract=package["architecture_contract"],
            review_contract=package["review_contract"],
            architecture_packet=package["architecture_packet"],
            review_set=package["review_set"],
            adjudication=low,
            realization_contract=package["realization_contract"],
        )


def test_legacy_composer_path_remains_backward_compatible() -> None:
    output = workspace("legacy")
    result = DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        app_id=GOLDEN_APP_ID,
    )
    assert result["composer_profile"] == "local-deep-v1"
    assert result["architecture"] == "modular-monolith-ddd-hexagonal"
    assert result["persistence"] == "sqlite-stdlib"
    assert "architecture_pattern_id" not in result
    assert not (generated_root(output) / "evidence/architecture").exists()


@pytest.mark.parametrize("pattern_id", EXECUTABLE_PATTERNS)
def test_reviewed_architecture_drives_generation_and_passes_conformance(pattern_id: str) -> None:
    output = workspace(f"governed-{pattern_id.lower()}")
    package = reviewed_package(pattern_id)
    result = DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        app_id=GOLDEN_APP_ID,
        architecture_package=package,
    )
    root = generated_root(output)
    assert result["architecture_pattern_id"] == pattern_id
    assert result["architecture_adapter_id"] == package["reviewed_freeze"]["adapter_id"]
    assert result["architecture_freeze_digest"] == package["reviewed_freeze"]["freeze_digest"]
    assert result["architecture_reviewed_decision_digest"] == package["reviewed_decision"]["reviewed_decision_digest"]
    assert result["architecture_conformance_digest"]
    assert result["llm_runtime_calls"] == 0
    assert result["real_payment_calls"] == "disabled"
    for relative in realization_contract()["common_generated_evidence_paths"]:
        assert (root / relative).is_file()
    for relative in realization_contract()["common_generated_document_paths"]:
        assert (root / relative).is_file()
    conformance = json.loads(
        (root / "evidence/architecture/architecture_conformance.json").read_text(
            encoding="utf-8"
        )
    )
    assert conformance["status"] == "PASS"
    assert verify_architecture_conformance_report(
        conformance,
        root,
        package["reviewed_freeze"],
        package["realization_contract"],
    )


def test_workflow_adapter_materializes_executable_workflow_contract() -> None:
    output = workspace("workflow")
    package = reviewed_package("WORKFLOW_CENTRIC_MODULAR_MONOLITH")
    DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        architecture_package=package,
    )
    path = (
        generated_root(output)
        / f"app/{GOLDEN_APP_ID}/application/workflows/dispute_workflow.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "HUMAN_REVIEW_STATES" in text
    assert "DEADLINE_POLICY" in text
    assert "REENTRY_POLICY" in text


def test_event_adapter_materializes_versioned_events_and_idempotent_outbox_usage() -> None:
    output = workspace("event")
    package = reviewed_package("EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX")
    DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        architecture_package=package,
    )
    root = generated_root(output)
    events = (
        root / f"app/{GOLDEN_APP_ID}/application/events.py"
    ).read_text(encoding="utf-8")
    outbox = (
        root / f"app/{GOLDEN_APP_ID}/infrastructure/messaging/outbox.py"
    ).read_text(encoding="utf-8")
    service = (
        root / f"app/{GOLDEN_APP_ID}/application/services/dispute_service.py"
    ).read_text(encoding="utf-8")
    assert "EVENT_SCHEMA_VERSION" in events
    assert "InMemoryOutbox" in outbox
    assert "idempotency_key" in outbox
    assert "InMemoryOutbox" in service
    assert "append" in service


def test_requirements_hash_mismatch_fails_before_publication() -> None:
    output = workspace("requirements-mismatch")
    package = reviewed_package("MODULAR_MONOLITH_HEXAGONAL")
    changed = deepcopy(requirements_ir())
    changed["c3_tamper"] = True
    with pytest.raises(DeepComposerError):
        DeepApplicationComposer(ROOT).compose(
            requirements_ir=changed,
            output_root=output,
            architecture_package=package,
        )
    assert not generated_root(output).exists()


def test_unsupported_reviewed_pattern_never_silently_falls_back() -> None:
    package = reviewed_package("MODULAR_MONOLITH_HEXAGONAL")
    bad = deepcopy(package)
    bad["adjudication"]["selected_candidate_id"] = "CQRS_EVENT_ORIENTED"
    bad["adjudication"]["status"] = "SELECTED_REVIEWED"
    bad["adjudication"]["adjudication_digest"] = canonical_sha256(
        {
            key: value
            for key, value in bad["adjudication"].items()
            if key != "adjudication_digest"
        }
    )
    with pytest.raises(ArchitectureDecisionError):
        build_reviewed_architecture_package(
            upstream_decision=bad["upstream_decision"],
            driver_ir=bad["driver_ir"],
            architecture_contract=bad["architecture_contract"],
            review_contract=bad["review_contract"],
            architecture_packet=bad["architecture_packet"],
            review_set=bad["review_set"],
            adjudication=bad["adjudication"],
            realization_contract=bad["realization_contract"],
        )


def test_conformance_validator_detects_domain_boundary_tampering() -> None:
    output = workspace("tamper-domain")
    package = reviewed_package("MODULAR_MONOLITH_HEXAGONAL")
    DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        architecture_package=package,
    )
    root = generated_root(output)
    domain = root / f"app/{GOLDEN_APP_ID}/domain/aggregates/dispute_case.py"
    domain.write_text(
        domain.read_text(encoding="utf-8")
        + "\nfrom app.upi_failed_debit_dispute.infrastructure.persistence import migrations\n",
        encoding="utf-8",
    )
    report = validate_architecture_conformance(
        root,
        package["reviewed_freeze"],
        package["realization_contract"],
    )
    assert report["status"] == "FAIL"
    assert "domain_does_not_import_infrastructure" in report["failed_rules"]


def test_conformance_validator_detects_missing_event_outbox() -> None:
    output = workspace("tamper-event")
    package = reviewed_package("EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX")
    DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        architecture_package=package,
    )
    root = generated_root(output)
    (
        root / f"app/{GOLDEN_APP_ID}/infrastructure/messaging/outbox.py"
    ).unlink()
    report = validate_architecture_conformance(
        root,
        package["reviewed_freeze"],
        package["realization_contract"],
    )
    assert report["status"] == "FAIL"
    assert "transactional_outbox_present" in report["failed_rules"]


def test_governed_generation_is_deterministic_for_same_ir_and_package() -> None:
    package = reviewed_package("WORKFLOW_CENTRIC_MODULAR_MONOLITH")
    output = workspace("deterministic")
    first = DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output / "one",
        architecture_package=package,
    )
    second = DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output / "two",
        architecture_package=package,
    )
    first_manifest = {
        item["path"]: item["sha256"]
        for item in first["file_manifest"]
        if item["path"] != "evidence/generation_manifest.json"
    }
    second_manifest = {
        item["path"]: item["sha256"]
        for item in second["file_manifest"]
        if item["path"] != "evidence/generation_manifest.json"
    }
    assert first_manifest == second_manifest


def test_adapter_registry_refuses_unknown_or_non_executable_pattern() -> None:
    contract = realization_contract()
    assert get_architecture_adapter(
        "MODULAR_MONOLITH_HEXAGONAL", contract
    ).adapter_id == "hexagonal_modular_monolith_v1"
    with pytest.raises(ArchitectureDecisionError):
        get_architecture_adapter("CQRS_EVENT_ORIENTED", contract)
    with pytest.raises(ArchitectureHumanGate):
        get_architecture_adapter("SERVICE_ORIENTED_DISTRIBUTED", contract)
