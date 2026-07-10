from __future__ import annotations

import subprocess
from pathlib import Path


class CandidateScopeError(RuntimeError):
    pass


def changed_paths(worktree: Path) -> set[str]:
    tracked = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--name-only", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "--others", "--exclude-standard"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    return {item for item in [*tracked, *untracked] if item}


def verify_exact_candidate_scope(worktree: Path, expected: set[str]) -> None:
    observed = changed_paths(worktree)
    if observed != expected:
        raise CandidateScopeError(
            f"Candidate scope mismatch: expected={sorted(expected)}, observed={sorted(observed)}"
        )
