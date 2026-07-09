from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.final_v1_candidate_consolidation import (
    BOUNDARY_FALSE_FIELDS,
    FINAL_EVIDENCE_INDEX_PATH,
    FINAL_MANIFEST_PATH,
    LOCAL_DEMO_INSTRUCTIONS_PATH,
    POLICY_PATH,
    PREPARED_FUTURE_TAG,
    PROMPT_PATH,
    RELEASE_GATE_PATH,
    VALIDATION_SUMMARY_PATH,
    build_final_v1_candidate_bundle,
    lifecycle_artifact_paths,
    safety_boundaries,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase45_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase45_final_v1_candidate_consolidation.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generator_cli_writes_final_candidate_artifacts() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_phase45_final_v1_candidate_consolidation.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "generated"
    assert report["future_tag_created"] is False
    assert report["certification_boundary"] == "certification_ready_not_certified"
    for path in lifecycle_artifact_paths():
        assert path.exists()


def test_final_candidate_manifest_and_gate_are_present_and_bounded() -> None:
    manifest = load_json(FINAL_MANIFEST_PATH)
    gate = load_json(RELEASE_GATE_PATH)
    assert manifest["candidate_status"] == "professional_stopping_point"
    assert manifest["prepared_future_tag"] == PREPARED_FUTURE_TAG
    assert manifest["future_tag_created"] is False
    assert gate["gate_id"] == "PHASE45-FINAL-V1-CANDIDATE-GATE"
    assert gate["automatic_release_actions_enabled"] is False


def test_committed_lifecycle_artifacts_match_builder() -> None:
    bundle = build_final_v1_candidate_bundle()
    assert load_json(FINAL_MANIFEST_PATH) == bundle["manifest"]
    assert load_json(RELEASE_GATE_PATH) == bundle["release_gate"]
    assert load_json(VALIDATION_SUMMARY_PATH) == bundle["validation_summary"]
    assert load_json(FINAL_EVIDENCE_INDEX_PATH) == bundle["final_evidence_index"]
    assert LOCAL_DEMO_INSTRUCTIONS_PATH.read_text(encoding="utf-8") == (
        bundle["local_demo_instructions"]
    )


def test_final_evidence_index_covers_required_groups() -> None:
    evidence = load_json(FINAL_EVIDENCE_INDEX_PATH)
    for group in [
        "final_candidate_artifacts",
        "policy_and_prompt",
        "validators_and_tests",
        "operator_portal_evidence",
        "generated_application_evidence",
        "release_evidence_bundle",
    ]:
        assert evidence[group]


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert boundaries["official_certification_claimed"] is False
    assert boundaries["official_certification_granted"] is False


def test_production_readiness_is_local_readiness_only() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    assert policy["production_readiness_claimed"] is False
    assert boundaries["production_readiness_claimed"] is False
    assert "local-readiness" in policy["production_readiness_scope"]
    assert "not_claimed" in policy["production_readiness_scope"]


def test_live_calls_secrets_deployment_merge_tag_push_are_disabled() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    for field in BOUNDARY_FALSE_FIELDS:
        assert policy[field] is False
        assert boundaries[field] is False


def test_external_ecosystem_integrations_remain_mocked_or_simulated() -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(FINAL_MANIFEST_PATH)
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert manifest["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_prompt_inherits_shared_contracts() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
