#!/usr/bin/env python3
"""Reusable governed phase-runner integration harness.

The runner converts validation command results into a deterministic repair plan
using the Phase 13AC governed self-healing classifier.

It intentionally does not execute risky repairs. It prepares an auditable plan
that future phase scripts can use to decide whether a local autonomous repair is
allowed or whether human governance escalation is required.

This file is intentionally executable both as:

    python -m scripts.governed_phase_runner
    python scripts/governed_phase_runner.py

The path-execution bootstrap is needed for operator handoff scripts and local
validators that execute files directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.governed_self_healing import (  # noqa: E402
    ClassifiedFailure,
    RepairDecision,
    classify_failure,
    enforce_iteration_limit,
)


@dataclass(frozen=True)
class GateCommand:
    """A validation gate command."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class GateResult:
    """Observed result from one validation gate."""

    name: str
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


@dataclass(frozen=True)
class RepairPlanItem:
    """One classified repair or escalation decision."""

    gate_name: str
    category: str
    decision: str
    action: str
    reason: str
    requires_human_approval: bool


@dataclass(frozen=True)
class GovernedPhaseRunPlan:
    """Auditable plan for a governed phase run."""

    phase: str
    max_repair_iterations: int
    gate_count: int
    failed_gate_count: int
    autonomous_repair_count: int
    human_escalation_count: int
    repair_items: tuple[RepairPlanItem, ...]

    @property
    def may_continue_autonomously(self) -> bool:
        return self.failed_gate_count > 0 and self.human_escalation_count == 0

    @property
    def requires_human_review(self) -> bool:
        return self.human_escalation_count > 0

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "schema_version": "governed-phase-run-plan.v1",
            "phase": self.phase,
            "max_repair_iterations": self.max_repair_iterations,
            "gate_count": self.gate_count,
            "failed_gate_count": self.failed_gate_count,
            "autonomous_repair_count": self.autonomous_repair_count,
            "human_escalation_count": self.human_escalation_count,
            "may_continue_autonomously": self.may_continue_autonomously,
            "requires_human_review": self.requires_human_review,
            "repair_items": [asdict(item) for item in self.repair_items],
        }


def run_gate(command: GateCommand, timeout_seconds: int = 120) -> GateResult:
    """Run one validation gate and capture its result."""

    completed = subprocess.run(
        command.command,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return GateResult(
        name=command.name,
        command=command.command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def classify_gate_result(result: GateResult) -> ClassifiedFailure | None:
    """Classify a failed gate result; passed gates return None."""

    if result.passed:
        return None
    return classify_failure(result.combined_output)


def build_governed_phase_run_plan(
    phase: str,
    results: Sequence[GateResult],
    max_repair_iterations: int = 5,
) -> GovernedPhaseRunPlan:
    """Build an auditable governed repair plan from gate results."""

    if not enforce_iteration_limit(0, max_repair_iterations):
        raise ValueError("max_repair_iterations does not permit any self-healing attempts")

    repair_items: list[RepairPlanItem] = []
    autonomous_count = 0
    escalation_count = 0

    for result in results:
        classification = classify_gate_result(result)
        if classification is None:
            continue

        if classification.decision is RepairDecision.AUTONOMOUS_REPAIR_ALLOWED:
            autonomous_count += 1
        else:
            escalation_count += 1

        repair_items.append(
            RepairPlanItem(
                gate_name=result.name,
                category=classification.category.value,
                decision=classification.decision.value,
                action=classification.action.value,
                reason=classification.reason,
                requires_human_approval=classification.requires_human_approval,
            )
        )

    failed_gate_count = sum(1 for result in results if not result.passed)

    return GovernedPhaseRunPlan(
        phase=phase,
        max_repair_iterations=max_repair_iterations,
        gate_count=len(results),
        failed_gate_count=failed_gate_count,
        autonomous_repair_count=autonomous_count,
        human_escalation_count=escalation_count,
        repair_items=tuple(repair_items),
    )


def write_audit_plan(plan: GovernedPhaseRunPlan, path: Path) -> None:
    """Write a governed phase-run plan as deterministic JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """CLI for classifying a single synthetic or captured failure text."""

    parser = argparse.ArgumentParser(description="Build a governed phase-run repair plan.")
    parser.add_argument("--phase", required=True)
    parser.add_argument("--gate-name", default="captured_failure")
    parser.add_argument("--failure-text", default="")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    result = GateResult(
        name=args.gate_name,
        command=("captured", args.gate_name),
        exit_code=1 if args.failure_text else 0,
        stdout=args.failure_text,
        stderr="",
    )
    plan = build_governed_phase_run_plan(args.phase, [result])

    if args.audit_out is not None:
        write_audit_plan(plan, args.audit_out)

    print(json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
