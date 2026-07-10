from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from factory.operator_portal.lifecycle_run_resolution import (
    LifecycleRunResolutionService,
)
from tools.lifecycle_orchestrator.repairs import latest_phase_run

STATES = [
    "PREFLIGHT_PASSED",
    "WORKTREE_READY",
    "IMPLEMENTED",
    "TARGETED_VALIDATED",
    "CANDIDATE_VERIFIED",
    "FULLY_VALIDATED",
    "POST_RESTORE_VALIDATED",
    "COMMITTED",
    "MERGED",
    "PUSHED",
    "CLOSED",
]


def command(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *argv],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def create_repo(path: Path) -> str:
    path.mkdir()
    command(path, "init", "-b", "main")
    command(path, "config", "user.email", "test@example.com")
    command(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("one\n", encoding="utf-8")
    command(path, "add", "tracked.txt")
    command(path, "commit", "-m", "initial")
    commit = command(path, "rev-parse", "HEAD")
    command(path, "update-ref", "refs/remotes/origin/main", commit)
    (path / "tools/lifecycle_orchestrator").mkdir(parents=True)
    return commit


def create_manifest(path: Path, phase: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "phase": phase,
                "feature_branch": f"phase{phase.lower()}/test",
                "commit_message": "test",
                "candidate_paths": ["tracked.txt"],
                "protected_actions": ["commit", "merge", "push"],
                "status": "ACTIVE",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def create_run(
    state_root: Path,
    run_id: str,
    *,
    phase: str,
    status: str,
    commit: str | None,
    manifest: Path,
) -> Path:
    run_dir = state_root / "lifecycle_runs" / run_id
    steps = run_dir / "steps"
    steps.mkdir(parents=True)
    completed = STATES if status == "CLOSED" else STATES[:3]
    evidence: dict[str, dict[str, str]] = {}
    for index, state in enumerate(completed, start=1):
        path = steps / f"{index:02d}_{state.lower()}.json"
        path.write_text(json.dumps({"state": state}) + "\n", encoding="utf-8")
        evidence[state] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    payload: dict[str, Any] = {
        "phase": phase,
        "run_id": run_id,
        "status": status,
        "current_state": "CLOSED" if status == "CLOSED" else "IMPLEMENTED",
        "base_commit": "base",
        "feature_commit": commit,
        "manifest_path": str(manifest),
        "manifest_digest": "same",
        "completed_states": completed,
        "step_evidence": evidence,
        "protected_actions_performed": (["commit", "merge", "push"] if status == "CLOSED" else []),
        "failure": None if status == "CLOSED" else {"message": "failed"},
        "tag_performed": False,
        "release_performed": False,
        "llm_calls": 0,
    }
    (run_dir / "run.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return run_dir


def test_campaign_and_portal_use_authoritative_closed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    commit = create_repo(repo)
    manifest = create_manifest(tmp_path / "phase46m.json", "46M")
    state_root = tmp_path / "state"
    closed = create_run(
        state_root,
        "46m-1",
        phase="46M",
        status="CLOSED",
        commit=commit,
        manifest=manifest,
    )
    create_run(
        state_root,
        "46m-2",
        phase="46M",
        status="FAILED",
        commit=None,
        manifest=manifest,
    )
    monkeypatch.setenv("UPI_APP_FACTORY_SOURCE_REPO", str(repo))
    assert latest_phase_run(state_root, "46M") == closed
    report = LifecycleRunResolutionService(
        project_root=repo,
        state_root=state_root,
    ).report("46M", expected_manifest_path=manifest)
    assert report["decision"] == "AUTHORITATIVE_CLOSED"
    assert report["selected_run"] == closed.name
    assert report["read_only"] is True
    assert report["mutation_performed"] is False
