from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import shutil
import subprocess

import pytest

from factory.application_engineering.deep_composer import GOLDEN_APP_ID
from scripts.run_phase59_60_deep_engineering_closure import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    FULL_REPOSITORY_TEST_TIMEOUT_SECONDS,
    command_timeout_seconds,
    failed_command_summaries,
    format_failed_command_details,
    run_command,
    sqlite_persistence_proof,
    write_generated_tests,
)
from scripts.validate_phase59_60_deep_engineering_closure import validate_report


ROOT = Path(__file__).resolve().parents[1]


def test_sqlite_persistence_proof_reopens_database(tmp_path: Path) -> None:
    app_root = ROOT / "workspace" / "deep_engineering_campaign" / "generated_app" / GOLDEN_APP_ID
    if not app_root.is_dir():
        pytest.skip("generated app is created by the closure runner")
    copied = tmp_path / GOLDEN_APP_ID
    shutil.copytree(app_root, copied)

    proof = sqlite_persistence_proof(tmp_path, copied)

    assert proof["integrity_check"] == "ok"
    assert proof["restart_row_count"] == 1
    assert proof["audit_chain_valid"] is True
    assert proof["pending_outbox_events"] == 1
    with sqlite3.connect(tmp_path / proof["db_path"]) as connection:
        assert connection.execute("SELECT state FROM dispute_cases").fetchone()[0] == "closed"


def test_generated_suite_file_contains_required_lifecycle_calls(tmp_path: Path) -> None:
    test_file = write_generated_tests(tmp_path)
    text = test_file.read_text(encoding="utf-8")

    for route_function in [
        "UPI_APP_FACTORY_ROOT_CONFTEST_ACTIVE",
        "create_dispute",
        "post_validation",
        "post_evidence",
        "post_investigation",
        "post_resolution",
        "post_closure",
        "get_timeline",
        "get_audit",
        "metrics",
    ]:
        assert route_function in text


def test_final_report_validator_fails_closed_on_no_go(tmp_path: Path) -> None:
    report_dir = tmp_path / "workspace" / "deep_engineering_campaign"
    report_dir.mkdir(parents=True)
    (report_dir / "final_report.json").write_text(
        json.dumps(
            {
                "stage": "Phases 59-60",
                "status": "blocked",
                "product_name": "UPI App Factory",
                "repository_id": "upi_app_factory",
                "mandatory_gates": {"all_commands_passed": False},
            }
        ),
        encoding="utf-8",
    )
    (report_dir / "final_report.md").write_text("blocked", encoding="utf-8")
    (report_dir / "promotion_decision.env").write_text("PROMOTION_DECISION=NO_GO\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="closure did not complete"):
        validate_report(tmp_path)


def test_full_repository_pytest_command_receives_extended_timeout() -> None:
    assert (
        command_timeout_seconds(["/repo/.venv/bin/python", "-m", "pytest", "-q"])
        == FULL_REPOSITORY_TEST_TIMEOUT_SECONDS
    )


def test_focused_pytest_and_non_pytest_commands_retain_default_timeout() -> None:
    assert (
        command_timeout_seconds(["/repo/.venv/bin/python", "-m", "pytest", "tests/test_example.py", "-q"])
        == DEFAULT_COMMAND_TIMEOUT_SECONDS
    )
    assert (
        command_timeout_seconds(
            ["/repo/.venv/bin/python", "-m", "pytest", "-q", "tests/test_example.py"]
        )
        == DEFAULT_COMMAND_TIMEOUT_SECONDS
    )
    assert (
        command_timeout_seconds(["/repo/.venv/bin/python", "-m", "ruff", "check", "."])
        == DEFAULT_COMMAND_TIMEOUT_SECONDS
    )


def test_run_command_returns_structured_timeout_evidence(tmp_path: Path) -> None:
    def timeout_run(
        args: object,
        *,
        cwd: Path,
        env: object,
        text: object,
        stdout: object,
        stderr: object,
        timeout: int,
        check: object,
    ) -> subprocess.CompletedProcess[str]:
        del args, cwd, env, text, stdout, stderr, check
        raise subprocess.TimeoutExpired(
            cmd=["python", "-m", "pytest", "-q"],
            timeout=timeout,
            output="line before timeout\nlast timeout line",
        )

    result = run_command(
        ["python", "-m", "pytest", "-q"],
        tmp_path,
        timeout=DEFAULT_COMMAND_TIMEOUT_SECONDS,
        run_impl=timeout_run,
    )

    assert result["command"] == "python -m pytest -q"
    assert result["returncode"] == 124
    assert result["passed"] is False
    assert result["duration_seconds"] >= 0
    assert "timed out after 240 seconds" in result["output_tail"]
    assert "last timeout line" in result["output_tail"]


def test_failed_command_report_evidence_retains_diagnostic_tail() -> None:
    failed_commands = failed_command_summaries(
        [
            {
                "command": "python -m pytest -q",
                "returncode": 1,
                "duration_seconds": 12.345,
                "passed": False,
                "output_tail": "FAILED tests/test_example.py::test_contract - AssertionError",
            }
        ]
    )

    assert failed_commands == [
        {
            "command": "python -m pytest -q",
            "returncode": 1,
            "duration_seconds": 12.345,
            "output_tail": "FAILED tests/test_example.py::test_contract - AssertionError",
        }
    ]

    details = format_failed_command_details(failed_commands)

    assert "returncode=1" in details
    assert "duration_seconds=12.345" in details
    assert "FAILED tests/test_example.py::test_contract - AssertionError" in details


def test_final_report_validator_preserves_failed_command_evidence(tmp_path: Path) -> None:
    report_dir = tmp_path / "workspace" / "deep_engineering_campaign"
    report_dir.mkdir(parents=True)
    (report_dir / "final_report.json").write_text(
        json.dumps(
            {
                "stage": "Phases 59-60",
                "status": "blocked",
                "product_name": "UPI App Factory",
                "repository_id": "upi_app_factory",
                "mandatory_gates": {"all_commands_passed": False},
                "failed_commands": [
                    {
                        "command": "python -m pytest -q",
                        "returncode": 1,
                        "duration_seconds": 12.345,
                        "output_tail": (
                            "FAILED tests/test_example.py::test_contract - AssertionError"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError) as exc_info:
        validate_report(tmp_path)

    message = str(exc_info.value)
    assert "closure did not complete" in message
    assert "returncode=1" in message
    assert "duration_seconds=12.345" in message
    assert "FAILED tests/test_example.py::test_contract - AssertionError" in message
