from __future__ import annotations

from pathlib import Path

from factory.prerequisite_artifacts import (
    materialize_clean_clone_test_evidence,
    restore_mutable_test_roots,
    snapshot_mutable_test_roots,
)


ROOT = Path(__file__).resolve().parents[1]


def test_materializer_can_scope_to_single_phase(tmp_path: Path) -> None:
    target = tmp_path / "lifecycle_artifacts"

    result = materialize_clean_clone_test_evidence(
        ROOT,
        target_root=target,
        include_phases={"phase28"},
    )

    assert result["status"] == "PASSED"
    assert result["files_declared"] == 7
    assert result["files_copied"] == 7
    assert result["files_existing"] == 0
    assert (target / "phase28" / "certification_boundary.json").is_file()
    assert not (target / "phase17").exists()


def test_mutable_runtime_snapshot_restores_changed_files_and_removes_new_paths(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    runtime_root = project_root / "workspace" / "deep_engineering_campaign"
    recipient_root = project_root / "factory_governance" / "phase68_70" / "recipient_replay_output"
    original_runtime = runtime_root / "generated_app" / "fixture.txt"
    original_recipient = recipient_root / "recipient_replay_result.json"

    original_runtime.parent.mkdir(parents=True, exist_ok=True)
    recipient_root.mkdir(parents=True, exist_ok=True)
    original_runtime.write_text("original-runtime\n", encoding="utf-8")
    original_recipient.write_text('{"status": "PASS"}\n', encoding="utf-8")

    snapshot = snapshot_mutable_test_roots(project_root)
    assert snapshot["status"] == "SNAPSHOTTED"

    original_runtime.write_text("mutated-runtime\n", encoding="utf-8")
    original_recipient.unlink()
    new_runtime_path = runtime_root / "phase58_portal_runtime" / "approved_runs" / "new.json"
    new_runtime_path.parent.mkdir(parents=True, exist_ok=True)
    new_runtime_path.write_text('{"residue": true}\n', encoding="utf-8")

    restored = restore_mutable_test_roots(snapshot)
    assert restored["status"] == "RESTORED"
    assert original_runtime.read_text(encoding="utf-8") == "original-runtime\n"
    assert original_recipient.read_text(encoding="utf-8") == '{"status": "PASS"}\n'
    assert not new_runtime_path.exists()
