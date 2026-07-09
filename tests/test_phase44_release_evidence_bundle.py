from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.release_evidence_bundle import (
    BOUNDARY_FALSE_FIELDS,
    EVIDENCE_INDEX_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    RELEASE_MANIFEST_PATH,
    RUN_INSTRUCTIONS_PATH,
    SUPPLY_CHAIN_PATH,
    build_release_evidence_bundle,
    lifecycle_artifact_paths,
    safety_boundaries,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase44_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase44_release_evidence_bundle.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generator_cli_writes_reviewable_directory_bundle() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_phase44_release_evidence_bundle.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "generated"
    assert report["zip_export_created"] is False
    assert report["certification_boundary"] == "certification_ready_not_certified"
    for path in lifecycle_artifact_paths():
        assert path.exists()


def test_bundle_contains_required_release_evidence_sections() -> None:
    manifest = load_json(RELEASE_MANIFEST_PATH)
    evidence_index = load_json(EVIDENCE_INDEX_PATH)
    assert manifest["bundle_format"] == "directory_artifacts"
    for section in [
        "manifests",
        "policy summaries",
        "validation summaries",
        "evidence index",
        "run instructions",
        "boundary statements",
    ]:
        assert section in manifest["included_sections"]
    for group in [
        "manifests",
        "policy_and_prompt",
        "validation_evidence",
        "operator_portal_evidence",
        "generated_application_evidence",
        "boundary_and_supply_chain",
    ]:
        assert evidence_index[group]


def test_bundle_builder_matches_committed_lifecycle_artifacts() -> None:
    bundle = build_release_evidence_bundle()
    assert load_json(RELEASE_MANIFEST_PATH) == bundle["manifest"]
    assert load_json(SUPPLY_CHAIN_PATH) == bundle["supply_chain"]
    assert RUN_INSTRUCTIONS_PATH.read_text(encoding="utf-8") == bundle["run_instructions"]


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert boundaries["certification_boundary"] == "certification_ready_not_certified"
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert boundaries["official_certification_claimed"] is False
    assert boundaries["official_certification_granted"] is False


def test_production_readiness_is_not_claimed_beyond_local_readiness_scope() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    assert policy["production_readiness_claimed"] is False
    assert boundaries["production_readiness_claimed"] is False
    assert "local-readiness" in policy["production_readiness_scope"]
    assert "local-readiness" in boundaries["production_readiness_scope"]


def test_live_provider_calls_real_secrets_and_release_actions_are_disabled() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    for field in BOUNDARY_FALSE_FIELDS:
        assert policy[field] is False
        assert boundaries[field] is False


def test_external_ecosystem_integrations_remain_mocked_or_simulated() -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(RELEASE_MANIFEST_PATH)
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert manifest["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_supply_chain_status_truthfully_reflects_local_tool_availability() -> None:
    supply_chain = load_json(SUPPLY_CHAIN_PATH)
    available = [tool for tool in supply_chain["checked_tools"] if shutil.which(tool)]
    if available:
        assert supply_chain["status"] == "available"
        assert {entry["tool"] for entry in supply_chain["available_tools"]} == set(available)
    else:
        assert supply_chain["status"] == "unavailable"
        assert supply_chain["available_tools"] == []
    assert supply_chain["sbom_generated"] is False
    assert supply_chain["external_network_calls_allowed"] is False


def test_prompt_inherits_shared_contracts() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
