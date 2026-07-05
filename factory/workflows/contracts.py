"""Small, explicit contracts for governed workflow orchestration.

The contracts intentionally use simple dataclasses so that new contributors can
inspect a workflow run without learning a framework first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowStep:
    """A deterministic step in the governed factory workflow."""

    step_id: str
    title: str
    agent_id: str
    requirement_ids: list[str]
    task_ids: list[str]
    policy_ids: list[str]
    evidence_refs: list[str]
    requires_human_review: bool = False


@dataclass(frozen=True)
class WorkflowRunResult:
    """Location and status for a completed workflow run."""

    run_id: str
    run_dir: Path
    status: str
