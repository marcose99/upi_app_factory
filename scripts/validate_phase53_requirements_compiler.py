#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REQUIRED_FILES = [
    "factory/application_engineering/requirements_compiler.py",
    "factory/application_engineering/schemas/requirements_ir.schema.json",
    "tests/fixtures/phase53/failed_debit_requirements.md",
    "tests/test_phase53_requirements_compiler.py",
    "workspace/deep_engineering_campaign/phase53_report.json",
    "workspace/deep_engineering_campaign/phase53_report.md",
]


def read_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def canonical_python(root: Path) -> Path:
    candidates = [
        root / ".venv" / "bin" / "python3",
        root / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
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
        raise AssertionError(f"Missing Phase 53 artifacts: {missing}")
    report = read_json(root / "workspace/deep_engineering_campaign/phase53_report.json")
    if report.get("stage") != "Phase 53":
        raise AssertionError("Phase 53 report JSON has the wrong stage")
    if report.get("llm_runtime_calls") != 0:
        raise AssertionError("Phase 53 report must prove zero runtime LLM calls")


def validate_compiler(root: Path, python: Path) -> None:
    fixture = root / "tests/fixtures/phase53/failed_debit_requirements.md"
    output = root / "workspace/deep_engineering_campaign/phase53_requirements_ir.json"
    module = "factory.application_engineering.requirements_compiler"

    compile_result = run(
        [
            str(python),
            "-m",
            module,
            "compile",
            "--input",
            str(fixture),
            "--project-root",
            str(root),
            "--output",
            str(output),
        ],
        root,
    )
    if compile_result.returncode != 0:
        raise AssertionError(compile_result.stdout)

    ir = read_json(output)
    if ir.get("ir_version") != "requirements-ir/v1":
        raise AssertionError("Compiled IR has the wrong version")
    app = ir.get("application")
    if not isinstance(app, dict) or app.get("app_id") != "upi_app_factory":
        raise AssertionError("Compiled IR does not preserve canonical app id")
    diagnostics = ir.get("diagnostics")
    if not isinstance(diagnostics, list):
        raise AssertionError("Compiled IR diagnostics must be a list")
    blocking = [item for item in diagnostics if isinstance(item, dict) and item.get("severity") in {"critical", "error"}]
    if blocking:
        raise AssertionError(f"Compiled fixture has blocking diagnostics: {blocking}")
    requirements = ir.get("requirements")
    if not isinstance(requirements, dict):
        raise AssertionError("Compiled IR requirements must be an object")
    required = {
        "actors",
        "use_cases",
        "bounded_contexts",
        "commands",
        "queries",
        "events",
        "aggregates",
        "invariants",
        "workflows",
        "apis",
        "data",
        "security",
        "operations",
        "evidence",
    }
    empty = [key for key in sorted(required) if not requirements.get(key)]
    if empty:
        raise AssertionError(f"Compiled IR has empty required collections: {empty}")

    validate_result = run(
        [str(python), "-m", module, "validate", "--input", str(fixture), "--project-root", str(root)],
        root,
    )
    if validate_result.returncode != 0 or "Requirements compiler validation passed" not in validate_result.stdout:
        raise AssertionError(validate_result.stdout)

    explain_result = run(
        [str(python), "-m", module, "explain", "--input", str(fixture), "--project-root", str(root)],
        root,
    )
    if explain_result.returncode != 0 or "Canonical hash" not in explain_result.stdout:
        raise AssertionError(explain_result.stdout)


def validate_tests(root: Path, python: Path) -> None:
    result = run([str(python), "-m", "pytest", "tests/test_phase53_requirements_compiler.py"], root)
    if result.returncode != 0:
        raise AssertionError(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    python = canonical_python(root)
    validate_artifacts(root)
    validate_compiler(root, python)
    validate_tests(root, python)
    print(
        "Phase 53 requirements compiler validation passed: deterministic compile, validate, "
        "explain CLI, failed-debit fixture, traceability, diagnostics, and reports are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
