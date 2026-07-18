#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REQUIRED_FILES = [
    "factory/application_engineering/local_platform_kernel.py",
    "tests/test_phase54_local_platform_kernel.py",
    "tests/architecture/test_phase54_kernel_architecture.py",
    "scripts/validate_phase54_local_platform_kernel.py",
    "docs/phase54/local_platform_kernel_architecture.md",
    "workspace/deep_engineering_campaign/phase54_report.json",
    "workspace/deep_engineering_campaign/phase54_report.md",
]

REQUIRED_SOURCE_MARKERS = [
    "class TypedId",
    "class Money",
    "class DeterministicIdGenerator",
    "class SQLiteConnectionFactory",
    "class SQLiteMigrator",
    "class SQLiteUnitOfWork",
    "class IdempotencyStore",
    "class AuditLog",
    "class TransactionalOutbox",
    "class JsonRedactingFormatter",
    "class MetricsRegistry",
    "class HealthRegistry",
    "class ProblemResponse",
    "class FictionalLocalAuthorizer",
    "def deterministic_evidence_bundle",
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


def canonical_python(root: Path) -> Path:
    for candidate in [root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python", Path(sys.executable)]:
        if candidate.is_file():
            return candidate
    raise AssertionError("No canonical Python interpreter found")


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
        raise AssertionError(f"Missing Phase 54 artifacts: {missing}")

    report = read_json(root / "workspace/deep_engineering_campaign/phase54_report.json")
    if report.get("stage") != "Phase 54":
        raise AssertionError("Phase 54 report JSON has the wrong stage")
    if report.get("llm_runtime_calls") != 0:
        raise AssertionError("Phase 54 report must prove zero runtime LLM calls")
    if report.get("real_payment_calls") != "disabled":
        raise AssertionError("Phase 54 report must prove real payment calls are disabled")


def validate_source(root: Path) -> None:
    source = (root / "factory/application_engineering/local_platform_kernel.py").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_SOURCE_MARKERS if marker not in source]
    if missing:
        raise AssertionError(f"Kernel source is missing required markers: {missing}")
    if "import sqlite3" not in source:
        raise AssertionError("Kernel must use standard-library sqlite3")
    lowered = source.lower()
    present = [term for term in PROHIBITED_TERMS if term in lowered]
    if present:
        raise AssertionError(f"Kernel source references prohibited dependency terms: {present}")


def validate_tests(root: Path, python: Path) -> None:
    result = run(
        [
            str(python),
            "-m",
            "pytest",
            "tests/test_phase54_local_platform_kernel.py",
            "tests/architecture/test_phase54_kernel_architecture.py",
        ],
        root,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    if "13 passed" not in result.stdout:
        raise AssertionError(f"Unexpected Phase 54 test count/output:\n{result.stdout}")


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
        "Phase 54 local platform kernel validation passed: sqlite migrations, rollback, "
        "concurrency, idempotency replay, audit tamper detection, outbox atomicity, "
        "redaction, authorization denial, metrics, reports, and architecture rules are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
