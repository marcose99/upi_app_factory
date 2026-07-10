from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


REQUIRED_CLOSED_STATES = frozenset(
    {
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
    }
)

MANIFEST_IDENTITY_FIELDS = (
    "phase",
    "feature_branch",
    "commit_message",
    "candidate_paths",
    "protected_actions",
)


class RunResolutionError(RuntimeError):
    """Raised when lifecycle evidence is invalid or ambiguous."""


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RunResolutionError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_contains(project_root: Path, ref: str, commit: str) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "merge-base",
            "--is-ancestor",
            commit,
            ref,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def phase_run_directories(state_root: Path, phase: str) -> list[Path]:
    lifecycle_root = state_root / "lifecycle_runs"
    if not lifecycle_root.is_dir():
        return []
    return sorted(
        path
        for path in lifecycle_root.glob(f"{phase.lower()}-*")
        if path.is_dir() and (path / "run.json").is_file()
    )


def _manifest_identity(path: Path) -> dict[str, object]:
    value = _load_object(path)
    return {
        field: value.get(field)
        for field in MANIFEST_IDENTITY_FIELDS
    }


def _manifest_matches(
    run: dict[str, Any],
    expected_manifest_path: Path | None,
) -> bool:
    if expected_manifest_path is None:
        return True
    raw_path = run.get("manifest_path")
    if not isinstance(raw_path, str):
        return False
    observed = Path(raw_path)
    if not observed.is_file() or not expected_manifest_path.is_file():
        return False
    return _manifest_identity(observed) == _manifest_identity(
        expected_manifest_path
    )


def _step_evidence_valid(run: dict[str, Any]) -> bool:
    evidence = run.get("step_evidence")
    if not isinstance(evidence, dict):
        return False
    if not REQUIRED_CLOSED_STATES.issubset(evidence):
        return False
    for state in REQUIRED_CLOSED_STATES:
        record = evidence.get(state)
        if not isinstance(record, dict):
            return False
        raw_path = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(raw_path, str) or not isinstance(
            expected_hash,
            str,
        ):
            return False
        path = Path(raw_path)
        if not path.is_file() or _sha256(path) != expected_hash:
            return False
    return True


def _protected_actions_valid(run: dict[str, Any]) -> bool:
    actions = run.get("protected_actions_performed")
    if not isinstance(actions, list):
        return False
    if not all(isinstance(item, str) for item in actions):
        return False
    return set(actions).issubset({"commit", "merge", "push"})


def _valid_closed_run(
    run: dict[str, Any],
    *,
    phase: str,
    project_root: Path,
    expected_manifest_path: Path | None,
    expected_base_commit: str | None,
) -> bool:
    if run.get("phase") != phase:
        return False
    if run.get("status") != "CLOSED":
        return False
    if run.get("current_state") != "CLOSED":
        return False
    if run.get("failure") not in (None, {}):
        return False

    completed = run.get("completed_states")
    if not isinstance(completed, list):
        return False
    if not REQUIRED_CLOSED_STATES.issubset(completed):
        return False

    if (
        expected_base_commit is not None
        and run.get("base_commit") != expected_base_commit
    ):
        return False

    feature_commit = run.get("feature_commit")
    if not isinstance(feature_commit, str) or not feature_commit:
        return False
    if not _git_contains(project_root, "main", feature_commit):
        return False
    if not _git_contains(project_root, "origin/main", feature_commit):
        return False

    if run.get("tag_performed") is True:
        return False
    if run.get("release_performed") is True:
        return False
    if run.get("llm_calls", 0) != 0:
        return False
    if not _protected_actions_valid(run):
        return False
    if not _step_evidence_valid(run):
        return False
    return _manifest_matches(run, expected_manifest_path)


def authoritative_closed_phase_run(
    state_root: Path,
    phase: str,
    *,
    project_root: Path,
    expected_manifest_path: Path | None = None,
    expected_base_commit: str | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    valid: list[tuple[Path, dict[str, Any]]] = []
    for run_dir in phase_run_directories(state_root, phase):
        run = _load_object(run_dir / "run.json")
        if _valid_closed_run(
            run,
            phase=phase,
            project_root=project_root,
            expected_manifest_path=expected_manifest_path,
            expected_base_commit=expected_base_commit,
        ):
            valid.append((run_dir, run))

    if not valid:
        return None

    identities = {
        (
            str(run.get("base_commit")),
            str(run.get("feature_commit")),
            str(run.get("manifest_digest")),
        )
        for _, run in valid
    }
    if len(identities) != 1:
        raise RunResolutionError(
            f"Conflicting authoritative CLOSED runs exist for {phase}"
        )
    return valid[-1]


def preferred_phase_run(
    state_root: Path,
    phase: str,
    *,
    project_root: Path,
    expected_manifest_path: Path | None = None,
    expected_base_commit: str | None = None,
) -> Path | None:
    authoritative = authoritative_closed_phase_run(
        state_root,
        phase,
        project_root=project_root,
        expected_manifest_path=expected_manifest_path,
        expected_base_commit=expected_base_commit,
    )
    if authoritative is not None:
        return authoritative[0]
    runs = phase_run_directories(state_root, phase)
    return runs[-1] if runs else None


def resolution_report(
    state_root: Path,
    phase: str,
    *,
    project_root: Path,
    expected_manifest_path: Path | None = None,
    expected_base_commit: str | None = None,
) -> dict[str, object]:
    runs = phase_run_directories(state_root, phase)
    authoritative = authoritative_closed_phase_run(
        state_root,
        phase,
        project_root=project_root,
        expected_manifest_path=expected_manifest_path,
        expected_base_commit=expected_base_commit,
    )
    selected = authoritative[0] if authoritative is not None else None
    return {
        "schema_version": 1,
        "phase": phase,
        "decision": (
            "AUTHORITATIVE_CLOSED"
            if selected is not None
            else "NO_AUTHORITATIVE_CLOSED_RUN"
        ),
        "selected_run": selected.name if selected is not None else None,
        "observed_runs": [path.name for path in runs],
        "non_selected_runs": [
            path.name for path in runs if selected is None or path != selected
        ],
        "mutation_performed": False,
    }
