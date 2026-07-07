from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_autonomous_quality_gate_pipeline_hardening import (
    DEFAULT_AUDIT_PATH,
    build_autonomous_quality_gate_pipeline_hardening,
    read_only_gate_specs,
    validate_autonomous_quality_gate_pipeline_hardening,
)


def test_phase14v_audit_preserves_governance_boundaries() -> None:
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=False,
        max_workers=1,
        timeout_seconds=30,
    )
    assert audit["quality_gate_pipeline_hardening_enabled"] is True
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_push_performed"] is False
    assert audit["official_certification_claimed"] is False
    assert audit["factory_does_not_self_certify"] is True


def test_phase14v_gate_specs_cover_required_pipeline_tiers() -> None:
    specs = read_only_gate_specs()
    gate_ids = {spec.gate_id for spec in specs}
    tiers = {spec.tier for spec in specs}
    assert "phase14u_artifact_validator" in gate_ids
    assert "phase14t_artifact_validator" in gate_ids
    assert "ruff_static_hygiene" in gate_ids
    assert "mypy_static_typing" in gate_ids
    assert "phase_artifact_validators" in tiers
    assert "static_hygiene" in tiers
    assert "static_typing" in tiers
    assert all(spec.read_only for spec in specs)
    assert all(spec.parallel_safe for spec in specs)


def test_phase14v_validator_accepts_well_formed_non_executed_audit() -> None:
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=False,
        max_workers=1,
        timeout_seconds=30,
    )
    assert validate_autonomous_quality_gate_pipeline_hardening(audit) == []


def test_phase14v_validator_rejects_boundary_violation() -> None:
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=False,
        max_workers=1,
        timeout_seconds=30,
    )
    audit["auto_push_performed"] = True
    errors = validate_autonomous_quality_gate_pipeline_hardening(audit)
    assert "auto_push_performed must be false" in errors


def test_phase14v_runner_writes_tmp_audit_without_touching_default_audit(tmp_path: Path) -> None:
    before = DEFAULT_AUDIT_PATH.read_text(encoding="utf-8") if DEFAULT_AUDIT_PATH.exists() else None
    audit_path = tmp_path / "phase14v-audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_autonomous_quality_gate_pipeline_hardening.py",
            "--audit-out",
            str(audit_path),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "AUTONOMOUS_QUALITY_GATE_PIPELINE_HARDENING_READY" in completed.stdout
    loaded = json.loads(audit_path.read_text(encoding="utf-8"))
    assert loaded["phase"] == "14V"
    after = DEFAULT_AUDIT_PATH.read_text(encoding="utf-8") if DEFAULT_AUDIT_PATH.exists() else None
    assert after == before


def test_phase14v_validation_requires_full_regression_tier() -> None:
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=False,
        max_workers=1,
        timeout_seconds=30,
    )
    audit["gate_tiers"] = ["syntax_compile", "static_hygiene"]
    errors = validate_autonomous_quality_gate_pipeline_hardening(audit)
    assert "gate_tiers must include full_regression" in errors


def test_phase14v_documents_legacy_clean_tree_regression_repair_class() -> None:
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=False,
        max_workers=1,
        timeout_seconds=30,
    )
    assert "legacy_drift_guardrail_clean_tree_regression" in audit["safe_repair_classes_known"]
    assert audit["full_regression_requires_clean_committed_tree"] is True
    assert audit["final_non_mutating_verification_only_after_final_audit_commit"] is True
