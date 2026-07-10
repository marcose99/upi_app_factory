from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    CREATED = "CREATED"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    WORKTREE_READY = "WORKTREE_READY"
    IMPLEMENTED = "IMPLEMENTED"
    TARGETED_VALIDATED = "TARGETED_VALIDATED"
    CANDIDATE_VERIFIED = "CANDIDATE_VERIFIED"
    FULLY_VALIDATED = "FULLY_VALIDATED"
    POST_RESTORE_VALIDATED = "POST_RESTORE_VALIDATED"
    COMMITTED = "COMMITTED"
    MERGED = "MERGED"
    PUSHED = "PUSHED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


STATE_ORDER: tuple[LifecycleState, ...] = (
    LifecycleState.CREATED,
    LifecycleState.PREFLIGHT_PASSED,
    LifecycleState.WORKTREE_READY,
    LifecycleState.IMPLEMENTED,
    LifecycleState.TARGETED_VALIDATED,
    LifecycleState.CANDIDATE_VERIFIED,
    LifecycleState.FULLY_VALIDATED,
    LifecycleState.POST_RESTORE_VALIDATED,
    LifecycleState.COMMITTED,
    LifecycleState.MERGED,
    LifecycleState.PUSHED,
    LifecycleState.CLOSED,
)


@dataclass(frozen=True)
class ApprovalSet:
    commit: bool = False
    merge: bool = False
    push: bool = False
    tag: bool = False
    release: bool = False

    @classmethod
    def from_csv(cls, text: str) -> "ApprovalSet":
        normalized = {
            item.strip().lower()
            for item in text.split(",")
            if item.strip()
        }
        allowed = {"commit", "merge", "push", "tag", "release"}
        unknown = normalized - allowed
        if unknown:
            raise ValueError(
                "Unknown approval actions: " + ", ".join(sorted(unknown))
            )
        return cls(
            commit="commit" in normalized,
            merge="merge" in normalized,
            push="push" in normalized,
            tag="tag" in normalized,
            release="release" in normalized,
        )

    def approved(self, action: str) -> bool:
        if action not in {"commit", "merge", "push", "tag", "release"}:
            raise ValueError(f"Unknown protected action: {action}")
        return bool(getattr(self, action))

    def to_dict(self) -> dict[str, bool]:
        return {
            "commit": self.commit,
            "merge": self.merge,
            "push": self.push,
            "tag": self.tag,
            "release": self.release,
        }


@dataclass(frozen=True)
class CommandResult:
    name: str
    argv: list[str]
    returncode: int
    duration_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    metrics: dict[str, Any]
    log_file: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": self.argv,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "metrics": self.metrics,
            "log_file": self.log_file,
        }
