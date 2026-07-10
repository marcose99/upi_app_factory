from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.lifecycle_orchestrator.maintenance import (
    LifecycleMaintenanceError,
    supersede_failed_run,
)


def test_supersede_preserves_and_hides_failed_run(tmp_path: Path) -> None:
    state = tmp_path / "state"
    run_dir = state / "lifecycle_runs/46t-test"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "46t-test",
                "phase": "46T",
                "status": "FAILED",
                "feature_commit": None,
                "protected_actions_performed": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = supersede_failed_run(
        state_root=state,
        run_id="46t-test",
        reason="test",
        evidence_export_dir=tmp_path / "exports",
        approved=True,
    )
    assert result["discoverable"] is False
    assert not (run_dir / "run.json").exists()
    assert (run_dir / "run.superseded.json").is_file()
    assert Path(str(result["archive"])).is_file()


def test_supersede_requires_explicit_approval(tmp_path: Path) -> None:
    with pytest.raises(LifecycleMaintenanceError):
        supersede_failed_run(
            state_root=tmp_path,
            run_id="missing",
            reason="test",
            evidence_export_dir=tmp_path,
            approved=False,
        )
