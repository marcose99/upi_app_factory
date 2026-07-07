from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.build_governed_self_healing_repair_catalog import (
    BLOCKED,
    CATALOG_ITEMS,
    READY,
    build_governed_repair_catalog,
    validate_governed_repair_catalog,
    write_governed_repair_catalog,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_repair_catalog_without_token_is_blocked_and_safe() -> None:
    catalog = build_governed_repair_catalog(Path.cwd())
    assert catalog.ready is False
    assert catalog.catalog_status == BLOCKED
    assert catalog.real_generated_application_deleted is False
    assert catalog.real_generated_application_overwritten is False
    assert catalog.destructive_execution_performed is False
    assert catalog.factory_self_healing_repair_applied is False
    assert catalog.factory_self_modification_applied is False
    assert validate_governed_repair_catalog(catalog) == []


def test_repair_catalog_with_token_and_operator_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
    assert catalog.ready is True
    assert catalog.catalog_status == READY
    assert catalog.fresh_recipient_replay_ready is True
    assert catalog.self_engineering_proposals_valid is True


def test_repair_catalog_has_all_required_items(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
    names = {item.name for item in catalog.catalog_items}
    assert names == set(CATALOG_ITEMS)
    assert all(item.satisfied for item in catalog.catalog_items)


def test_repair_classes_are_human_gated_and_not_auto_applied(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
    assert len(catalog.repair_classes) >= 5
    assert all(not repair.auto_apply_allowed_in_this_phase for repair in catalog.repair_classes)
    assert all(repair.human_approval_required for repair in catalog.repair_classes)
    assert all(repair.rollback_required for repair in catalog.repair_classes)
    assert all(repair.required_evidence for repair in catalog.repair_classes)
    assert all(repair.required_validation_gates for repair in catalog.repair_classes)


def test_repair_catalog_contains_future_low_risk_candidates(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
    candidates = [
        repair
        for repair in catalog.repair_classes
        if repair.risk_tier == "low" and repair.auto_apply_eligible_in_future
    ]
    assert candidates


def test_repair_catalog_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
    output = tmp_path / "repair_catalog.json"
    write_governed_repair_catalog(catalog, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "governed-self-healing-repair-catalog.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["factory_self_healing_repair_applied"] is False
    assert payload["factory_self_modification_applied"] is False


def test_repair_catalog_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_governed_self_healing_repair_catalog.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ready"] is False


def test_repair_catalog_cli_with_token_and_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_governed_self_healing_repair_catalog.py",
            "--project-root",
            str(Path.cwd()),
            "--approval-token",
            str(token_path),
            "--operator-confirms-final-human-approval",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["catalog_status"] == READY
    assert payload["ready"] is True


def test_phase13ar_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ar_self_healing_repair_catalog.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AR governed self-healing repair catalog artifacts validated." in result.stdout
