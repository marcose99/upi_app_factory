#!/usr/bin/env python3
"""Check whether a future phase automation script adopts governed self-healing."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


RUNNER_MARKERS = (
    "scripts/governed_phase_runner.py",
    "scripts.governed_phase_runner",
    "build_governed_phase_run_plan",
    "GovernedPhaseRunPlan",
)

EQUIVALENT_CONTROL_MARKER = "GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL"

EQUIVALENT_REQUIRED_PHRASES = (
    "classify",
    "unknown",
    "human",
    "post-repair",
    "audit",
)

BLOCKED_BYPASS_PATTERNS = (
    "skip mypy",
    "skip ruff",
    "skip pytest",
    "ignore governance",
    "auto approve release",
    "disable policy",
    "bypass gate",
)


@dataclass(frozen=True)
class AdoptionCheckResult:
    """Result of a governed self-healing adoption check."""

    script_path: str
    compliant: bool
    uses_governed_runner: bool
    declares_equivalent_control: bool
    blocked_bypass_patterns: tuple[str, ...]
    missing_equivalent_phrases: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _contains_any(text: str, markers: Sequence[str]) -> bool:
    return any(marker in text for marker in markers)


def evaluate_script_text(script_text: str, script_path: str = "<memory>") -> AdoptionCheckResult:
    """Evaluate script text against the Phase 13AE adoption policy."""

    lowered = script_text.lower()
    blocked = tuple(pattern for pattern in BLOCKED_BYPASS_PATTERNS if pattern in lowered)

    uses_runner = _contains_any(script_text, RUNNER_MARKERS)
    declares_equivalent = EQUIVALENT_CONTROL_MARKER in script_text

    missing_equivalent_phrases: tuple[str, ...] = ()
    if declares_equivalent:
        missing_equivalent_phrases = tuple(
            phrase for phrase in EQUIVALENT_REQUIRED_PHRASES if phrase not in lowered
        )

    if blocked:
        return AdoptionCheckResult(
            script_path=script_path,
            compliant=False,
            uses_governed_runner=uses_runner,
            declares_equivalent_control=declares_equivalent,
            blocked_bypass_patterns=blocked,
            missing_equivalent_phrases=missing_equivalent_phrases,
            reason="Script contains blocked governance bypass pattern(s).",
        )

    if uses_runner:
        return AdoptionCheckResult(
            script_path=script_path,
            compliant=True,
            uses_governed_runner=True,
            declares_equivalent_control=declares_equivalent,
            blocked_bypass_patterns=(),
            missing_equivalent_phrases=missing_equivalent_phrases,
            reason="Script uses the governed phase runner.",
        )

    if declares_equivalent and not missing_equivalent_phrases:
        return AdoptionCheckResult(
            script_path=script_path,
            compliant=True,
            uses_governed_runner=False,
            declares_equivalent_control=True,
            blocked_bypass_patterns=(),
            missing_equivalent_phrases=(),
            reason="Script declares equivalent governed self-healing controls.",
        )

    if declares_equivalent:
        return AdoptionCheckResult(
            script_path=script_path,
            compliant=False,
            uses_governed_runner=False,
            declares_equivalent_control=True,
            blocked_bypass_patterns=(),
            missing_equivalent_phrases=missing_equivalent_phrases,
            reason="Equivalent control declaration is incomplete.",
        )

    return AdoptionCheckResult(
        script_path=script_path,
        compliant=False,
        uses_governed_runner=False,
        declares_equivalent_control=False,
        blocked_bypass_patterns=(),
        missing_equivalent_phrases=(),
        reason="Script does not use the governed runner or declare equivalent controls.",
    )


def evaluate_script_path(path: Path) -> AdoptionCheckResult:
    """Evaluate one script file."""

    if not path.exists():
        return AdoptionCheckResult(
            script_path=str(path),
            compliant=False,
            uses_governed_runner=False,
            declares_equivalent_control=False,
            blocked_bypass_patterns=(),
            missing_equivalent_phrases=(),
            reason="Script path does not exist.",
        )

    text = path.read_text(encoding="utf-8")
    return evaluate_script_text(text, str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check governed self-healing adoption.")
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args()

    result = evaluate_script_path(args.script)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"{args.script}: {'PASS' if result.compliant else 'FAIL'} - {result.reason}")

    return 0 if result.compliant else 1


if __name__ == "__main__":
    raise SystemExit(main())
