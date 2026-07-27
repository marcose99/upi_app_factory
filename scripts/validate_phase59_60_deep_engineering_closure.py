#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPORT_JSON = Path("workspace/deep_engineering_campaign/final_report.json")
REPORT_MD = Path("workspace/deep_engineering_campaign/final_report.md")
PROMOTION_ENV = Path("workspace/deep_engineering_campaign/promotion_decision.env")


def canonical_python(root: Path) -> Path:
    for candidate in (root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidate.is_file():
            return candidate
    raise AssertionError("canonical Python interpreter not found")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def format_failed_command_details(failed_commands: list[dict[str, Any]]) -> str:
    details: list[str] = []
    for item in failed_commands:
        output_tail = str(item.get("output_tail", "")).strip()
        if len(output_tail) > 1200:
            output_tail = output_tail[-1200:]
        details.append(
            "command={command!r}, returncode={returncode}, duration_seconds={duration_seconds}, "
            "output_tail={output_tail!r}".format(
                command=item.get("command", ""),
                returncode=item.get("returncode"),
                duration_seconds=item.get("duration_seconds"),
                output_tail=output_tail,
            )
        )
    return "; failed command evidence: [" + "; ".join(details) + "]"


def failed_command_details(report: dict[str, Any]) -> str:
    failed_commands = report.get("failed_commands", [])
    if not isinstance(failed_commands, list):
        return ""
    typed_failures = [item for item in failed_commands if isinstance(item, dict)]
    if not typed_failures:
        return ""
    return format_failed_command_details(typed_failures)


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(root / REPORT_JSON)
    if report.get("stage") != "Phases 59-60":
        raise AssertionError("final report has the wrong stage")
    if (
        report.get("product_name") != "UPI App Factory"
        or report.get("repository_id") != "upi_app_factory"
    ):
        raise AssertionError("governed identity was not preserved")
    if report.get("status") != "completed":
        details = failed_command_details(report)
        raise AssertionError(
            f"closure did not complete: {report.get('mandatory_gates')}{details}"
        )
    gates = report.get("mandatory_gates", {})
    if not gates or not all(gates.values()):
        raise AssertionError(f"mandatory gates failed closed: {gates}")
    depth = report.get("verification", {}).get("depth_score", {})
    if (
        depth.get("overall", 0) < 80
        or depth.get("domain_fidelity", 0) < 16
        or depth.get("security_privacy", 0) < 12
        or depth.get("testing_depth", 0) < 12
    ):
        raise AssertionError(f"depth gate failed: {depth}")
    if depth.get("critical_findings") != 0 or depth.get("high_findings") != 0:
        raise AssertionError(f"unresolved critical/high findings: {depth}")
    if report.get("promotion_decision") != "GO_FOR_HUMAN_REVIEW":
        raise AssertionError("human-review promotion decision was not produced")
    if any(
        action not in report.get("actions_not_performed", [])
        for action in ["commit", "merge", "push", "tag", "release", "deploy"]
    ):
        raise AssertionError("actions-not-performed evidence is incomplete")
    if not (root / REPORT_MD).is_file() or not (root / PROMOTION_ENV).is_file():
        raise AssertionError("final Markdown report or promotion env is missing")
    env_text = (root / PROMOTION_ENV).read_text(encoding="utf-8")
    if (
        "PROMOTION_DECISION=GO_FOR_HUMAN_REVIEW" not in env_text
        or "PROHIBITED_ACTIONS_PERFORMED=0" not in env_text
    ):
        raise AssertionError("promotion env did not fail closed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-heavy", action="store_true")
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    python = canonical_python(root)
    command = [str(python), "scripts/run_phase59_60_deep_engineering_closure.py"]
    if parsed.skip_heavy:
        command.append("--skip-heavy")
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    report = validate_report(root)
    print(
        "Phases 59-60 deep engineering closure validation passed: "
        f"{len(report.get('command_results', []))} commands recorded, "
        f"depth score {report['verification']['depth_score']['overall']}, "
        "GO_FOR_HUMAN_REVIEW."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
