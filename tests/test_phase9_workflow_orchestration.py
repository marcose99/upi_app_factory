from __future__ import annotations

import json
from pathlib import Path

from factory.workflows.state_machine import run_workflow
from scripts.validate_workflow_run import validate_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase9_workflow_run_is_traceable(tmp_path: Path) -> None:
    run_dir = run_workflow(
        project_root=PROJECT_ROOT,
        run_id="pytest_phase9_workflow_run",
        output_root=tmp_path,
        force=True,
    ).run_dir

    errors = validate_run(run_dir)
    assert errors == []

    manifest = json.loads((run_dir / "workflow_run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "passed"
    assert manifest["step_count"] == 7
    assert manifest["completed_step_count"] == 7
    assert "MISSING_OFFICIAL_SOURCE" in manifest["honesty_labels"]


def test_phase9_workflow_can_record_paused_checkpoint_state(tmp_path: Path) -> None:
    run_dir = run_workflow(
        project_root=PROJECT_ROOT,
        run_id="pytest_phase9_paused_workflow_run",
        output_root=tmp_path,
        force=True,
        stop_after_step="WF-P9-003",
    ).run_dir

    errors = validate_run(run_dir)
    assert errors == []

    state = json.loads((run_dir / "workflow_state.json").read_text(encoding="utf-8"))
    resume = json.loads((run_dir / "workflow_resume_report.json").read_text(encoding="utf-8"))

    assert state["status"] == "paused"
    assert state["completed_steps"] == ["WF-P9-001", "WF-P9-002", "WF-P9-003"]
    assert state["blocked_steps"][0] == "WF-P9-004"
    assert resume["can_resume"] is True
    assert resume["resume_from_step_id"] == "WF-P9-004"
