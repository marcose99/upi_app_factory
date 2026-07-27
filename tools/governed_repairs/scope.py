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
        check=False,
    )
    if tracked.returncode != 0:
        raise CandidateScopeError(tracked.stderr.strip() or "git diff failed")
    untracked = subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "--others", "--exclude-standard"],
        text=True,
        capture_output=True,
        check=False,
    )
    if untracked.returncode != 0:
        raise CandidateScopeError(untracked.stderr.strip() or "git ls-files failed")
    return {item for item in [*tracked.stdout.splitlines(), *untracked.stdout.splitlines()] if item}


def verify_exact_candidate_scope(worktree: Path, expected: set[str]) -> None:
    try:
        observed = changed_paths(worktree)
    except CandidateScopeError as exc:
        message = str(exc).lower()
        if "blocked_by_governed" not in message and "not a git repository" not in message:
            raise
        missing = sorted(path for path in expected if not (worktree / path).is_file())
        if missing:
            raise CandidateScopeError(f"Cannot verify governed fallback scope; missing={missing}") from exc
        observed = set(expected)
    if observed != expected:
        raise CandidateScopeError(
            f"Candidate scope mismatch: expected={sorted(expected)}, observed={sorted(observed)}"
        )
