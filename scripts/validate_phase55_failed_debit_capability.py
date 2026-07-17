#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REQUIRED_FILES = [
    "factory/application_engineering/failed_debit_capability.py",
    "tests/test_phase55_failed_debit_capability.py",
    "workspace/deep_engineering_campaign/phase55_failed_debit_capability_ir.json",
    "workspace/deep_engineering_campaign/phase55_report.json",
    "workspace/deep_engineering_campaign/phase55_report.md",
    "scripts/validate_phase55_failed_debit_capability.py",
]

REQUIRED_SOURCE_MARKERS = [
    "class DisputeCase",
    "class DisputeId",
    "class TransactionReference",
    "class Money",
    "class DisputeReason",
    "class CaseVersion",
    "class EvidenceItem",
    "class ResolutionDecision",
    "TRANSITION_TABLE",
    "class EligibilityPolicy",
    "class DuplicateCasePolicy",
    "class EvidenceCompletenessPolicy",
    "class ResolutionPolicy",
    "class DisputeApplicationService",
    "class DisputeCaseRepositoryPort",
    "class InMemoryIdempotencyPort",
    "OptimisticConcurrencyError",
]

PROHIBITED_TERMS = [
    "sqlalchemy",
    "psycopg",
    "pymysql",
    "redis",
    "kafka",
    "rabbitmq",
    "elasticsearch",
    "kubernetes",
    "terraform",
    "docker",
]


def read_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def read_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AssertionError(f"{label} must be a JSON object")
    return value


def read_string_sequence(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssertionError(f"{label} must be a JSON string list")
    return value


def canonical_python(root: Path) -> Path:
    for candidate in [root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python"]:
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def run(command: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def validate_artifacts(root: Path) -> None:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise AssertionError(f"Missing Phase 55 artifacts: {missing}")

    report = read_json(root / "workspace/deep_engineering_campaign/phase55_report.json")
    if report.get("stage") != "Phase 55":
        raise AssertionError("Phase 55 report JSON has the wrong stage")
    if report.get("product_name") != "UPI App Factory":
        raise AssertionError("Phase 55 report must preserve the product name")
    if report.get("repository_id") != "upi_app_factory":
        raise AssertionError("Phase 55 report must preserve the repository id")
    if report.get("llm_runtime_calls") != 0:
        raise AssertionError("Phase 55 report must prove zero runtime LLM calls")
    if report.get("real_payment_calls") != "disabled":
        raise AssertionError("Phase 55 report must prove real payment calls are disabled")

    ir = read_json(root / "workspace/deep_engineering_campaign/phase55_failed_debit_capability_ir.json")
    domain = read_mapping(ir.get("domain"), "IR domain")
    states = set(read_string_sequence(domain.get("states"), "IR domain states"))
    expected_states = {
        "received",
        "validated",
        "evidence_pending",
        "investigation",
        "resolution_proposed",
        "resolved",
        "rejected",
        "closed",
    }
    if states != expected_states:
        raise AssertionError(f"IR states do not match the required lifecycle: {states}")


def validate_source(root: Path) -> None:
    source = (root / "factory/application_engineering/failed_debit_capability.py").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_SOURCE_MARKERS if marker not in source]
    if missing:
        raise AssertionError(f"Failed-debit capability source is missing required markers: {missing}")
    lowered = source.lower()
    present = [term for term in PROHIBITED_TERMS if term in lowered]
    if present:
        raise AssertionError(f"Capability source references prohibited dependency terms: {present}")
    if "case_type: str = \"failed_debit_no_credit\"" not in source:
        raise AssertionError("DisputeCase must lock the failed-debit case type")
    if "currency != \"INR\"" not in source or "amount <= decimal.Decimal(\"0.00\")" not in source:
        raise AssertionError("Money must enforce positive INR amounts")


def validate_tests(root: Path, python: Path) -> None:
    result = run([str(python), "-m", "pytest", "tests/test_phase55_failed_debit_capability.py", "-q"], root)
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    if "19 passed" not in result.stdout:
        raise AssertionError(f"Unexpected Phase 55 test count/output:\n{result.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    python = canonical_python(root)

    validate_artifacts(root)
    validate_source(root)
    validate_tests(root, python)
    print(
        "Phase 55 failed-debit capability validation passed: aggregate, value objects, "
        "transition guards, policies, events, application commands/queries/ports/services, "
        "authorization, idempotency, replay, concurrency, fuzz invariants, IR, and reports are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
