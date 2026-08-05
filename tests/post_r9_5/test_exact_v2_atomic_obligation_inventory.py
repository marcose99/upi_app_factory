from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.exact_v2_traceability import (
    CANONICAL_APPLICATION_ID,
    COMPATIBILITY_APPLICATION_ID,
    REQUIREMENTS_TEXT_SHA256,
    TRACKED_APPLICATION_ROOT,
    build_atomic_obligation_inventory,
    build_generated_application_artifact_payloads,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITATIVE_TEXT = Path(
    Path.home()
    / "Downloads"
    / "upi_app_factory_post_r9_13_r10.kufLlk"
    / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.txt"
)


def _test_reference_exists(nodeid: str) -> bool:
    relative_path, _, target = nodeid.partition("::")
    path = ROOT / relative_path
    if not path.is_file():
        return False
    if not target:
        return True
    text = path.read_text(encoding="utf-8")
    return all(fragment in text for fragment in target.split("::"))


def _evidence_path(evidence_reference: str) -> Path:
    if evidence_reference.startswith("workspace/"):
        return ROOT / evidence_reference
    return TRACKED_APPLICATION_ROOT / evidence_reference


def _normalized_endpoint_signature(text: str) -> tuple[str, str] | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or parts[0] not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return None
    path = parts[1]
    if " or an equivalent" in path:
        path = path.split(" or an equivalent", 1)[0]
    if "?" in path:
        path = path.split("?", 1)[0]
    path = path.replace("{case_id}", "{dispute_id}")
    return parts[0], path


def test_atomic_inventory_is_rederived_from_the_authoritative_exact_text() -> None:
    assert AUTHORITATIVE_TEXT.is_file()
    exact_text = AUTHORITATIVE_TEXT.read_bytes()
    assert hashlib.sha256(exact_text).hexdigest() == REQUIREMENTS_TEXT_SHA256

    derived = build_atomic_obligation_inventory(AUTHORITATIVE_TEXT, project_root=ROOT)
    tracked = json.loads(
        (TRACKED_APPLICATION_ROOT / "evidence" / "atomic_obligation_inventory.json").read_text(
            encoding="utf-8"
        )
    )

    assert tracked["canonical_application_id"] == CANONICAL_APPLICATION_ID
    assert tracked["compatibility_application_id"] == COMPATIBILITY_APPLICATION_ID
    assert tracked["mandatory_obligation_count"] == 781
    assert tracked["decision"] == "NO_GO"
    assert derived["mandatory_obligation_count"] == tracked["mandatory_obligation_count"]
    assert derived["decision"] == tracked["decision"]
    for index in (0, 294, len(tracked["items"]) - 1):
        assert derived["items"][index]["obligation_id"] == tracked["items"][index]["obligation_id"]
        assert derived["items"][index]["normalized_text"] == tracked["items"][index]["normalized_text"]
        assert derived["items"][index]["source"] == tracked["items"][index]["source"]


def test_truthful_exact_v2_reports_fail_closed_when_partial_mandatory_items_exist() -> None:
    payloads = build_generated_application_artifact_payloads(ROOT)
    inventory = json.loads(payloads["evidence/atomic_obligation_inventory.json"])
    coverage = json.loads(payloads["evidence/coverage_report.json"])
    unsupported = json.loads(payloads["evidence/unsupported_obligation_report.json"])
    report = json.loads(payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"])
    matrix = json.loads(payloads["evidence/REQUIREMENT_CAPABILITY_MATRIX.json"])

    assert coverage["coverage_status"] == "NO_GO_UNSUPPORTED_MANDATORY_OBLIGATIONS"
    assert coverage["summary"]["obligation_count"] == 781
    assert coverage["summary"]["not_applicable_count"] == 3
    assert coverage["summary"]["partial_count"] > 0
    assert coverage["summary"]["supported_count"] > 0
    assert coverage["summary"]["mandatory_no_go_count"] == coverage["summary"]["partial_count"] + coverage["summary"]["unsupported_count"]
    assert unsupported["unsupported_obligation_count"] == coverage["summary"]["mandatory_no_go_count"]
    assert report["decision"] == "NO_GO_WITH_IMPROVEMENT_REQUIREMENTS"
    assert report["mandatory_gate_passed"] is False
    assert matrix["decision"] == report["decision"]
    assert any(item["support_status"] == "PARTIAL" for item in inventory["items"])
    assert any(item["support_status"] == "SUPPORTED" for item in inventory["items"])


def test_traceability_and_openapi_references_are_verified_against_real_files() -> None:
    payloads = build_generated_application_artifact_payloads(ROOT)
    traceability = json.loads(payloads["evidence/requirements_traceability_matrix.json"])
    openapi_inventory = json.loads(payloads["evidence/openapi_inventory.json"])

    endpoints = {
        (item["method"], item["path"])
        for item in openapi_inventory["endpoint_inventory"]
    }
    endpoint_obligations = 0
    for item in traceability["items"]:
        for implementation_ref in item["implementation_refs"]:
            assert (ROOT / implementation_ref["path"]).is_file()
        for test_ref in item["test_refs"]:
            assert _test_reference_exists(test_ref)
        for evidence_ref in item["evidence_refs"]:
            assert _evidence_path(evidence_ref).is_file()
        endpoint_signature = _normalized_endpoint_signature(item["normalized_text"])
        if endpoint_signature is not None:
            endpoint_obligations += 1
            assert endpoint_signature in endpoints

    assert endpoint_obligations >= 10
