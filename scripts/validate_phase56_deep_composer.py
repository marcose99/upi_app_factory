#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REQUIRED_FILES = [
    "factory/application_engineering/deep_composer.py",
    "tests/test_phase56_deep_composer.py",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/generation_manifest.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/openapi/openapi.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/docs/domain_state_machine.md",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/docs/threat_model.md",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/docs/operations_runbook.md",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/docs/test_plan.md",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/app/upi_failed_debit_dispute/interfaces/api/main.py",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/app/upi_failed_debit_dispute/infrastructure/persistence/migrations/0001_initial.sql",
    "workspace/deep_engineering_campaign/phase56_report.json",
    "workspace/deep_engineering_campaign/phase56_report.md",
    "scripts/validate_phase56_deep_composer.py",
]

REQUIRED_SOURCE_MARKERS = [
    "class DeepProfile",
    "class DeepApplicationComposer",
    "def compose(",
    "compose_golden_application",
    "local-deep-v1",
    "sqlite-stdlib",
    "upi_failed_debit_dispute",
    "llm_runtime_calls",
    "real_payment_calls",
]

REQUIRED_ENDPOINTS = {
    "GET /health",
    "GET /ready",
    "GET /metrics",
    "POST /v1/disputes",
    "GET /v1/disputes/{dispute_id}",
    "GET /v1/disputes",
    "POST /v1/disputes/{dispute_id}/evidence",
    "POST /v1/disputes/{dispute_id}/validation",
    "POST /v1/disputes/{dispute_id}/investigation",
    "POST /v1/disputes/{dispute_id}/resolution",
    "POST /v1/disputes/{dispute_id}/closure",
    "GET /v1/disputes/{dispute_id}/timeline",
    "GET /v1/disputes/{dispute_id}/audit",
}

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
]


def read_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def read_string_sequence(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssertionError(f"{label} must be a JSON string list")
    return value


def read_int(value: object, label: str) -> int:
    if not isinstance(value, int):
        raise AssertionError(f"{label} must be a JSON integer")
    return value


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
        raise AssertionError(f"Missing Phase 56 artifacts: {missing}")

    report = read_json(root / "workspace/deep_engineering_campaign/phase56_report.json")
    if report.get("stage") != "Phase 56":
        raise AssertionError("Phase 56 report JSON has the wrong stage")
    if report.get("product_name") != "UPI App Factory":
        raise AssertionError("Phase 56 report must preserve the product name")
    if report.get("repository_id") != "upi_app_factory":
        raise AssertionError("Phase 56 report must preserve the repository id")
    if report.get("llm_runtime_calls") != 0:
        raise AssertionError("Phase 56 report must prove zero runtime LLM calls")
    if report.get("real_payment_calls") != "disabled":
        raise AssertionError("Phase 56 report must prove real payment calls are disabled")

    manifest = read_json(
        root / "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/generation_manifest.json"
    )
    if manifest.get("app_id") != "upi_failed_debit_dispute":
        raise AssertionError("Golden generated app must use a non-default namespace")
    if manifest.get("composer_profile") != "local-deep-v1":
        raise AssertionError("Golden generated app must use the versioned deep profile")
    if manifest.get("persistence") != "sqlite-stdlib":
        raise AssertionError("Generated app must use standard-library SQLite persistence")
    if set(read_string_sequence(manifest.get("endpoints"), "Generated manifest endpoints")) != REQUIRED_ENDPOINTS:
        raise AssertionError("Generated app endpoint contract is incomplete")
    if manifest.get("llm_runtime_calls") != 0 or manifest.get("real_payment_calls") != "disabled":
        raise AssertionError("Generated manifest violates runtime safety controls")

    depth = read_json(root / "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/depth_score.json")
    if read_int(depth.get("overall"), "Depth score overall") < 80:
        raise AssertionError("Generated app depth score is below the campaign gate")
    if read_int(depth.get("critical_findings"), "Depth score critical findings") != 0 or read_int(
        depth.get("high_findings"), "Depth score high findings"
    ) != 0:
        raise AssertionError("Generated app has unresolved critical or high findings")


def validate_source(root: Path) -> None:
    source = (root / "factory/application_engineering/deep_composer.py").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_SOURCE_MARKERS if marker not in source]
    if missing:
        raise AssertionError(f"Deep composer source is missing required markers: {missing}")
    lowered = source.lower()
    present = [term for term in PROHIBITED_TERMS if term in lowered]
    if present:
        raise AssertionError(f"Deep composer source references prohibited dependency terms: {present}")

    generated_root = root / "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute"
    text_suffixes = {".json", ".md", ".py", ".sh", ".sql", ".env", ".txt"}
    generated_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in generated_root.rglob("*")
        if path.is_file() and (path.suffix in text_suffixes or path.name == "example.env")
    )
    generated_lowered = generated_text.lower()
    generated_present = [term for term in PROHIBITED_TERMS if term in generated_lowered]
    if generated_present:
        raise AssertionError(f"Generated app references prohibited dependency terms: {generated_present}")
    for marker in ["CREATE TABLE dispute_cases", "CREATE TABLE idempotency_records", "CREATE TABLE audit_records", "CREATE TABLE outbox_events"]:
        if marker not in generated_text:
            raise AssertionError(f"Generated SQLite migration missing marker: {marker}")


def validate_tests(root: Path, python: Path) -> None:
    result = run([str(python), "-m", "pytest", "tests/test_phase56_deep_composer.py", "-q"], root)
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    if "4 passed" not in result.stdout:
        raise AssertionError(f"Unexpected Phase 56 test count/output:\n{result.stdout}")


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
        "Phase 56 deep composer validation passed: versioned deep profile, deterministic golden app, "
        "non-default app namespace, required APIs, SQLite migration inventory, documentation, evidence, "
        "safety controls, and tests are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
