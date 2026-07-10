from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RepairContext:
    phase: str
    repair_id: str
    project_root: Path
    worktree: Path
    run_dir: Path
    manifest_path: Path
    candidate_paths: tuple[str, ...]
    diagnostics: str
    attempt: int
    max_attempts: int
    python: str


@dataclass(frozen=True)
class RepairDecision:
    repair_id: str
    eligible: bool
    reason: str
    affected_paths: tuple[str, ...] = ()
    diagnostic_fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepairResult:
    repair_id: str
    status: str
    changed_paths: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    validation: dict[str, Any]
    rollback_available: bool


class GovernedRepair(Protocol):
    repair_id: str

    def assess(self, context: RepairContext) -> RepairDecision: ...

    def apply(
        self,
        context: RepairContext,
        decision: RepairDecision,
    ) -> RepairResult: ...
