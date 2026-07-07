from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_local_agentic_ai_threat_tests import (
    EXPECTED_CONTROLS,
    READY,
    THREAT_FAMILIES,
    build_local_agentic_ai_threat_test_suite,
    build_threat_cases,
    evaluate_threat_case,
    validate_threat_test_suite,
    write_threat_test_suite,
)


def test_threat_cases_cover_all_required_families() -> None:
    cases = build_threat_cases()

    assert {case.family for case in cases} == set(THREAT_FAMILIES)
    assert {case.expected_control for case in cases} == set(EXPECTED_CONTROLS)
    assert all(case.local_only for case in cases)


def test_each_threat_case_evaluates_to_passed() -> None:
    cases = build_threat_cases()

    evaluations = [evaluate_threat_case(case) for case in cases]

    assert all(evaluation.passed for evaluation in evaluations)
    assert all("no_live_provider_call" in evaluation.evidence for evaluation in evaluations)
    assert all("call_external_system" in evaluation.blocked_actions_checked for evaluation in evaluations)


def test_sensitive_information_case_is_redacted() -> None:
    case = next(case for case in build_threat_cases() if case.family == "SENSITIVE_INFORMATION_DISCLOSURE")

    evaluation = evaluate_threat_case(case)

    assert evaluation.passed is True
    assert "[REDACTED]" in evaluation.sanitized_output
    assert "OPENAI_API_KEY" not in evaluation.sanitized_output


def test_tool_abuse_case_blocks_destructive_tool_request() -> None:
    case = next(case for case in build_threat_cases() if case.family == "TOOL_ABUSE")

    evaluation = evaluate_threat_case(case)

    assert evaluation.passed is True
    assert "unsafe_tool_call_blocked" in evaluation.evidence
    assert "delete_real_generated_application" in evaluation.blocked_actions_checked


def test_local_agentic_ai_threat_suite_is_ready() -> None:
    suite = build_local_agentic_ai_threat_test_suite(Path.cwd())

    assert suite.ready is True
    assert suite.suite_status == READY
    assert suite.all_threats_passed is True
    assert validate_threat_test_suite(suite) == []


def test_local_agentic_ai_threat_suite_is_non_destructive() -> None:
    suite = build_local_agentic_ai_threat_test_suite(Path.cwd())

    assert suite.live_provider_calls_performed is False
    assert suite.external_system_calls_performed is False
    assert suite.real_generated_application_deleted is False
    assert suite.real_generated_application_overwritten is False
    assert suite.factory_self_modification_applied is False
    assert suite.auto_merge_performed is False
    assert suite.auto_tag_performed is False
    assert suite.auto_release_performed is False


def test_threat_suite_audit_report_is_written(tmp_path: Path) -> None:
    suite = build_local_agentic_ai_threat_test_suite(Path.cwd())
    output = tmp_path / "threat_suite.json"

    write_threat_test_suite(suite, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "local-agentic-ai-threat-test-suite.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["all_threats_passed"] is True


def test_threat_suite_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_local_agentic_ai_threat_tests.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["suite_status"] == READY
    assert payload["ready"] is True


def test_phase13av_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13av_agentic_ai_threat_tests.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AV local agentic-AI threat-test artifacts validated." in result.stdout
