from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.run_generated_app_depth_release_evidence_batch import (
    DEFAULT_AUDIT_PATH,
    GENERATED_APP_DEPTH_ROADMAP,
    RELEASE_EVIDENCE_INDUSTRIALIZATION,
    build_generated_app_depth_release_evidence_batch,
)
from scripts.validate_phase14wx_generated_app_depth_release_evidence import (
    validate_generated_app_depth_release_evidence_batch,
)


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_phase14wx_audit_declares_combined_endgame_batch(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    audit = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=audit_path,
    )
    persisted = _load_json(audit_path)
    assert audit["phase"] == "14W-X"
    assert persisted["batch_phases"] == ["14W", "14X"]
    assert persisted["generated_application_depth_roadmap_executor_enabled"] is True
    assert persisted["release_evidence_industrialization_enabled"] is True


def test_phase14wx_depth_roadmap_is_substantive(tmp_path: Path) -> None:
    audit = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=tmp_path / "audit.json",
    )
    roadmap = audit["generated_application_depth_roadmap"]
    assert roadmap == GENERATED_APP_DEPTH_ROADMAP
    assert len(roadmap) >= 8
    assert "evidence_pack_traceability" in roadmap
    assert "negative_resilience_and_replay_scenarios" in roadmap


def test_phase14wx_release_evidence_is_industrialized(tmp_path: Path) -> None:
    audit = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=tmp_path / "audit.json",
    )
    evidence = audit["release_evidence_industrialization"]
    assert evidence == RELEASE_EVIDENCE_INDUSTRIALIZATION
    assert "quality_gate_matrix" in evidence
    assert "reproducible_handoff_evidence" in evidence


def test_phase14wx_preserves_human_gates_and_certification_boundary(tmp_path: Path) -> None:
    audit = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=tmp_path / "audit.json",
    )
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_push_performed"] is False
    assert audit["auto_release_performed"] is False
    assert audit["official_certification_claimed"] is False
    assert audit["official_certification_granted_by_factory"] is False
    assert "certifying_authority_review" in audit["what_sits_between_generated_application_and_certification"]


def test_phase14wx_tests_use_temporary_audit_outputs(tmp_path: Path) -> None:
    audit_path = tmp_path / "isolated" / "audit.json"
    build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=audit_path,
    )
    assert audit_path.exists()
    assert audit_path != DEFAULT_AUDIT_PATH


def test_phase14wx_validator_accepts_committed_artifacts() -> None:
    assert validate_generated_app_depth_release_evidence_batch() == []
