from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.demo_reviewer_pack import (
    SAFE_AUTOMATED_COMMAND_IDS,
    STAGED_COMMANDS,
    build_staged_command_report,
    reviewer_pack_sections,
    run_safe_checks,
    safety_boundaries,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase43_one_command_demo_reviewer_pack_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase43/one_command_demo_reviewer_pack_prompt.md"
REVIEWER_PACK_PATH = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/"
    "reviewer_pack.md"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase43_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase43_one_command_demo_reviewer_pack.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_one_command_prints_exact_staged_commands_by_default() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_phase43_one_command_demo_reviewer_pack.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "staged_commands"
    assert report["one_command"] == "make phase43-demo-reviewer-pack"
    assert [entry["command_id"] for entry in report["staged_commands"]] == [
        command.command_id for command in STAGED_COMMANDS
    ]


def test_reviewer_pack_sections_cover_required_topics() -> None:
    sections = reviewer_pack_sections()
    assert set(sections) == {
        "what_the_factory_does",
        "how_to_run_it",
        "what_evidence_to_inspect",
        "what_is_intentionally_mocked",
        "certification_ready_not_certified_boundary",
        "known_limitations",
    }
    reviewer_pack = REVIEWER_PACK_PATH.read_text(encoding="utf-8")
    for phrase in ["What The Factory Does", "How To Run It", "Known Limitations"]:
        assert phrase in reviewer_pack


def test_safe_checks_are_bounded_local_and_mock_only(tmp_path: Path) -> None:
    report = run_safe_checks(report_path=tmp_path / "phase43_report.json")
    assert report["status"] == "passed"
    assert [entry["command_id"] for entry in report["executed_command_results"]] == list(
        SAFE_AUTOMATED_COMMAND_IDS,
    )
    assert all(entry["return_code"] == 0 for entry in report["executed_command_results"])
    assert report["safety_boundaries"]["live_provider_calls_allowed"] is False
    assert report["safety_boundaries"]["external_ecosystem_integrations"] == (
        "mocked_or_simulated_only"
    )


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    assert policy["certification_boundary"] == "certification_ready_not_certified"
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


def test_live_provider_calls_and_real_secrets_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    for field in ["live_provider_calls_allowed", "real_secrets_allowed"]:
        assert policy[field] is False
        assert boundaries[field] is False


def test_deploy_merge_tag_push_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    boundaries = safety_boundaries()
    for field in ["deployment_allowed", "merge_allowed", "tag_allowed", "push_allowed"]:
        assert policy[field] is False
        assert boundaries[field] is False


def test_external_ecosystem_integrations_remain_mocked_or_simulated() -> None:
    policy = load_json(POLICY_PATH)
    report = build_staged_command_report()
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert report["safety_boundaries"]["external_ecosystem_integrations"] == (
        "mocked_or_simulated_only"
    )


def test_prompt_inherits_shared_contracts() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
