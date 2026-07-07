from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_autonomous_phase_discovery_and_planning import (
    DEFAULT_AUDIT_PATH,
    READY_STATUS,
    build_autonomous_phase_discovery_and_planning,
    validate_autonomous_phase_discovery_and_planning,
)


def test_phase14u_plan_discovers_remaining_endgame_sequence() -> None:
    audit = build_autonomous_phase_discovery_and_planning(execute_readonly_gates=False)
    assert audit["status"] == READY_STATUS
    assert audit["discovered_next_phase"] == "phase14v/autonomous-quality-gate-pipeline-hardening"
    assert audit["end_phase_target"] == "phase14z/v1-autonomous-readiness-pack"
    assert audit["planned_phase_count"] == 5
    assert validate_autonomous_phase_discovery_and_planning(audit) == []


def test_phase14u_preserves_human_gated_boundaries() -> None:
    audit = build_autonomous_phase_discovery_and_planning(execute_readonly_gates=False)
    for field in (
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_push_performed",
        "auto_release_performed",
        "auto_certification_performed",
        "live_provider_calls_performed",
        "destructive_cleanup_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
    ):
        assert audit[field] is False
    assert audit["human_approval_required_for_merge"] is True
    assert audit["human_approval_required_for_tag"] is True
    assert audit["human_approval_required_for_push"] is True
    assert audit["human_approval_required_for_release"] is True
    assert audit["factory_does_not_self_certify"] is True


def test_phase14u_known_safe_repair_classes_include_phase14t_learning() -> None:
    audit = build_autonomous_phase_discovery_and_planning(execute_readonly_gates=False)
    safe_classes = audit["safe_repair_classes_known"]
    assert "ruff_unused_import_cleanup" in safe_classes
    assert "mypy_redundant_cast_cleanup" in safe_classes
    assert "generated_app_runtime_cache_cleanup" in safe_classes


def test_phase14u_cli_writes_audit(tmp_path: Path) -> None:
    audit_path = tmp_path / "phase14u_audit.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_autonomous_phase_discovery_and_planning.py",
            "--audit-out",
            str(audit_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == READY_STATUS


def test_phase14u_validator_passes_after_audit_generation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_autonomous_phase_discovery_and_planning.py",
            "--audit-out",
            str(DEFAULT_AUDIT_PATH),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    validation = subprocess.run(
        [sys.executable, "scripts/validate_phase14u_autonomous_phase_discovery.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
