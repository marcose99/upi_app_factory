from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import shutil

import pytest

from factory.application_engineering.deep_composer import GOLDEN_APP_ID
from scripts.run_phase59_60_deep_engineering_closure import (
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
