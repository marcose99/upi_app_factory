from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.lifecycle_orchestrator.incident_replay import replay_duplicate_run_incident

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


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def setup_repo(path: Path) -> str:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "file.txt").write_text("x\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "base")
    commit = git(path, "rev-parse", "HEAD")
    git(path, "update-ref", "refs/remotes/origin/main", commit)
    return commit


def make_manifest(path: Path, phase: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "phase": phase,
                "feature_branch": f"phase{phase.lower()}/x",
                "commit_message": "x",
                "candidate_paths": ["file.txt"],
                "protected_actions": ["commit", "merge", "push"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def make_run(
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
    for index, state in enumerate(completed, 1):
        path = steps / f"{index:02d}.json"
        path.write_text(json.dumps({"state": state}) + "\n", encoding="utf-8")
        evidence[state] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    value: dict[str, Any] = {
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
    (run_dir / "run.json").write_text(json.dumps(value) + "\n", encoding="utf-8")
    return run_dir


def test_real_incident_shape_selects_closed_over_newer_failed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    commit = setup_repo(repo)
    manifest = make_manifest(tmp_path / "phase46m.json", "46M")
    state = tmp_path / "state"
    make_run(
        state,
        "46m-20260710-172548",
        phase="46M",
        status="CLOSED",
        commit=commit,
        manifest=manifest,
    )
    make_run(
        state,
        "46m-20260710-174905",
        phase="46M",
        status="FAILED",
        commit=None,
        manifest=manifest,
    )
    report = replay_duplicate_run_incident(
        state_root=state,
        project_root=repo,
        phase="46M",
        expected_manifest_path=manifest,
    )
    assert report["status"] == "AUTHORITATIVE_CLOSED_SELECTED"
    assert report["authoritative_run"] == "46m-20260710-172548"
    assert report["preferred_run"] == "46m-20260710-172548"
    assert report["mutation_performed"] is False
