from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from tools.lifecycle_orchestrator.run_resolution import (
    RunResolutionError,
    authoritative_closed_phase_run,
    preferred_phase_run,
    resolution_report,
)


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


def repository(path: Path) -> str:
    path.mkdir()
    command(path, "init", "-b", "main")
    command(path, "config", "user.email", "test@example.com")
    command(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("one\n", encoding="utf-8")
    command(path, "add", "tracked.txt")
    command(path, "commit", "-m", "initial")
    commit = command(path, "rev-parse", "HEAD")
    command(path, "update-ref", "refs/remotes/origin/main", commit)
    return commit


def manifest(path: Path, phase: str) -> Path:
    value = {
        "phase": phase,
        "feature_branch": f"phase{phase.lower()}/test",
        "commit_message": f"phase {phase}",
        "candidate_paths": ["tracked.txt"],
        "protected_actions": ["commit", "merge", "push"],
        "status": "ACTIVE",
    }
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def lifecycle_run(
    state_root: Path,
    run_id: str,
    *,
    phase: str,
    status: str,
    commit: str | None,
    base_commit: str,
    manifest_path: Path,
    tamper: bool = False,
    tag: bool = False,
    llm_calls: int = 0,
) -> Path:
    run_dir = state_root / "lifecycle_runs" / run_id
    steps = run_dir / "steps"
    steps.mkdir(parents=True)
    completed = STATES if status == "CLOSED" else STATES[:3]
    evidence: dict[str, dict[str, str]] = {}
    for index, state in enumerate(completed, start=1):
        evidence_path = steps / f"{index:02d}_{state.lower()}.json"
        evidence_path.write_text(
            json.dumps({"state": state}) + "\n",
            encoding="utf-8",
        )
        evidence[state] = {
            "path": str(evidence_path),
            "sha256": hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest(),
        }
    if tamper:
        first_path = Path(evidence[completed[0]]["path"])
        first_path.write_text("tampered\n", encoding="utf-8")

    run: dict[str, Any] = {
        "phase": phase,
        "run_id": run_id,
        "status": status,
        "current_state": (
            "CLOSED" if status == "CLOSED" else "IMPLEMENTED"
        ),
        "base_commit": base_commit,
        "feature_commit": commit,
        "manifest_path": str(manifest_path),
        "manifest_digest": run_id,
        "completed_states": completed,
        "step_evidence": evidence,
        "protected_actions_performed": (
            ["commit", "merge", "push"]
            if status == "CLOSED"
            else []
        ),
        "failure": (
            None if status == "CLOSED" else {"message": "failed"}
        ),
        "tag_performed": tag,
        "release_performed": False,
        "llm_calls": llm_calls,
    }
    (run_dir / "run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_dir


def test_closed_run_is_preferred_over_newer_failed_duplicate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    commit = repository(repo)
    phase_manifest = manifest(tmp_path / "phase46m.json", "46M")
    state_root = tmp_path / "state"
    closed = lifecycle_run(
        state_root,
        "46m-20260710-172548",
        phase="46M",
        status="CLOSED",
        commit=commit,
        base_commit="base",
        manifest_path=phase_manifest,
    )
    lifecycle_run(
        state_root,
        "46m-20260710-174905",
        phase="46M",
        status="FAILED",
        commit=None,
        base_commit=commit,
        manifest_path=phase_manifest,
    )
    assert preferred_phase_run(
        state_root,
        "46M",
        project_root=repo,
        expected_manifest_path=phase_manifest,
    ) == closed


def test_tampered_closed_evidence_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    commit = repository(repo)
    phase_manifest = manifest(tmp_path / "phase46m.json", "46M")
    state_root = tmp_path / "state"
    lifecycle_run(
        state_root,
        "46m-1",
        phase="46M",
        status="CLOSED",
        commit=commit,
        base_commit="base",
        manifest_path=phase_manifest,
        tamper=True,
    )
    failed = lifecycle_run(
        state_root,
        "46m-2",
        phase="46M",
        status="FAILED",
        commit=None,
        base_commit=commit,
        manifest_path=phase_manifest,
    )
    assert preferred_phase_run(
        state_root,
        "46M",
        project_root=repo,
        expected_manifest_path=phase_manifest,
    ) == failed


def test_conflicting_closed_runs_fail_closed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    first = repository(repo)
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    command(repo, "add", "tracked.txt")
    command(repo, "commit", "-m", "second")
    second = command(repo, "rev-parse", "HEAD")
    command(repo, "update-ref", "refs/remotes/origin/main", second)

    phase_manifest = manifest(tmp_path / "phase46x.json", "46X")
    state_root = tmp_path / "state"
    lifecycle_run(
        state_root,
        "46x-1",
        phase="46X",
        status="CLOSED",
        commit=first,
        base_commit="base-a",
        manifest_path=phase_manifest,
    )
    lifecycle_run(
        state_root,
        "46x-2",
        phase="46X",
        status="CLOSED",
        commit=second,
        base_commit="base-b",
        manifest_path=phase_manifest,
    )
    with pytest.raises(RunResolutionError):
        authoritative_closed_phase_run(
            state_root,
            "46X",
            project_root=repo,
            expected_manifest_path=phase_manifest,
        )


def test_tagged_or_llm_using_closed_run_is_rejected(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    commit = repository(repo)
    phase_manifest = manifest(tmp_path / "phase46z.json", "46Z")
    state_root = tmp_path / "state"
    lifecycle_run(
        state_root,
        "46z-1",
        phase="46Z",
        status="CLOSED",
        commit=commit,
        base_commit="base",
        manifest_path=phase_manifest,
        tag=True,
    )
    lifecycle_run(
        state_root,
        "46z-2",
        phase="46Z",
        status="CLOSED",
        commit=commit,
        base_commit="base",
        manifest_path=phase_manifest,
        llm_calls=1,
    )
    assert authoritative_closed_phase_run(
        state_root,
        "46Z",
        project_root=repo,
        expected_manifest_path=phase_manifest,
    ) is None


def test_resolution_report_is_non_mutating(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    commit = repository(repo)
    phase_manifest = manifest(tmp_path / "phase46m.json", "46M")
    state_root = tmp_path / "state"
    closed = lifecycle_run(
        state_root,
        "46m-1",
        phase="46M",
        status="CLOSED",
        commit=commit,
        base_commit="base",
        manifest_path=phase_manifest,
    )
    failed = lifecycle_run(
        state_root,
        "46m-2",
        phase="46M",
        status="FAILED",
        commit=None,
        base_commit=commit,
        manifest_path=phase_manifest,
    )
    before = {
        path: path.read_bytes()
        for path in state_root.rglob("*")
        if path.is_file()
    }
    report = resolution_report(
        state_root,
        "46M",
        project_root=repo,
        expected_manifest_path=phase_manifest,
    )
    after = {
        path: path.read_bytes()
        for path in state_root.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert report["decision"] == "AUTHORITATIVE_CLOSED"
    assert report["selected_run"] == closed.name
    assert report["non_selected_runs"] == [failed.name]
    assert report["mutation_performed"] is False
