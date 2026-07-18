#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


CANONICAL_ID = "upi_app_factory"
CANONICAL_NAME = "UPI App Factory"
FORBIDDEN_LABEL = "Factory" + "FromNothing"

REQUIRED_FILES = [
    "AGENTS.md",
    "pyproject.toml",
    "tools/identity_compat.py",
    "scripts/validate_phase47b_canonical_identity.py",
    "factory/application_engineering/portfolio.py",
    "factory/operator_portal/portfolio_api.py",
    "factory/operator_portal/runtime_api.py",
    "factory/operator_portal/runtime_contracts.py",
    "factory/operator_portal/runtime_evidence.py",
    "factory/operator_portal/runtime_network_policy.py",
    "factory/operator_portal/runtime_openapi.py",
    "factory/operator_portal/runtime_scenarios.py",
    "factory/operator_portal/runtime_store.py",
    "factory/operator_portal/runtime_supervisor.py",
    "tests/phase50/test_runtime_api.py",
    "tests/phase50/test_runtime_contracts.py",
    "tests/phase50/test_runtime_evidence.py",
    "tests/phase50/test_runtime_network_policy.py",
    "tests/phase50/test_runtime_openapi.py",
    "tests/phase50/test_runtime_scenarios.py",
    "tests/phase50/test_runtime_security.py",
    "tests/phase50/test_runtime_supervisor.py",
    "tests/phase51/test_catalogue_lineage.py",
    "tests/phase51/test_portal_api_ui.py",
    "tests/phase51/test_portfolio_contracts.py",
    "tests/phase51/test_portfolio_e2e.py",
    "tests/phase51/test_resilience_cleanup.py",
    "tests/phase51/test_runtime_allocation.py",
    "tests/phase51/test_security_guards.py",
    "tests/phase51/test_version_comparison_lifecycle.py",
]

GOVERNANCE_FILES = [
    "AGENTS.md",
    "docs/deployment/DEPLOYMENT_BOUNDARIES_AND_NON_CLAIMS.md",
    "docs/handover/README_HANDOVER.md",
]

BOUNDARY_PHRASES = [
    "mocked",
    "simulated",
    "certification",
    "production",
]

SOURCE_FORBIDDEN_TERMS = [
    "terraform apply",
    "kubectl apply",
    "twine upload",
    "secret create",
    "boto3",
    "google.cloud",
]


def tracked_files(root: Path) -> list[Path]:
    raw = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    return [
        root / item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\x00")
        if item
    ]


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"Unable to read required file {path}: {exc}")
        return ""


def validate_required_files(root: Path, errors: list[str]) -> None:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        errors.append(f"Missing Phase 52 foundation files: {missing}")


def validate_canonical_identity(root: Path, errors: list[str]) -> None:
    agents = read_text(root / "AGENTS.md", errors)
    pyproject = read_text(root / "pyproject.toml", errors)
    if CANONICAL_NAME not in agents or CANONICAL_ID not in agents:
        errors.append("AGENTS.md does not preserve canonical UPI App Factory identity")
    if 'name = "upi-app-factory"' not in pyproject:
        errors.append("pyproject.toml does not expose the canonical package name")


def validate_governance_boundaries(root: Path, errors: list[str]) -> None:
    joined = "\n".join(read_text(root / relative, errors) for relative in GOVERNANCE_FILES)
    lowered = joined.lower()
    for phrase in BOUNDARY_PHRASES:
        if phrase not in lowered:
            errors.append(f"Governance boundary evidence missing phrase: {phrase}")


def validate_test_inventory(root: Path, errors: list[str]) -> None:
    phase50_tests = sorted((root / "tests/phase50").glob("test_*.py"))
    phase51_tests = sorted((root / "tests/phase51").glob("test_*.py"))
    if len(phase50_tests) < 8:
        errors.append("Phase 52 foundation requires the Phase 50 runtime test inventory")
    if len(phase51_tests) < 8:
        errors.append("Phase 52 foundation requires the Phase 51 portfolio test inventory")


def validate_no_forbidden_content(root: Path, errors: list[str]) -> None:
    foundation_source = {
        relative
        for relative in REQUIRED_FILES
        if relative.startswith(("factory/", "tools/"))
    }
    for path in tracked_files(root):
        relative = path.relative_to(root).as_posix()
        if FORBIDDEN_LABEL in relative:
            errors.append(f"Forbidden project label in path: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if FORBIDDEN_LABEL in text:
            errors.append(f"Forbidden project label in content: {relative}")
        if relative in foundation_source:
            for term in SOURCE_FORBIDDEN_TERMS:
                if term in text:
                    errors.append(f"Forbidden live-operation term in source {relative}: {term}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()

    errors: list[str] = []
    validate_required_files(root, errors)
    validate_canonical_identity(root, errors)
    validate_governance_boundaries(root, errors)
    validate_test_inventory(root, errors)
    validate_no_forbidden_content(root, errors)

    if errors:
        raise SystemExit("\n".join(sorted(set(errors))))

    print(
        "Phase 52 deep engineering foundation validation passed: canonical identity, "
        "runtime and portfolio foundations, deterministic test inventory, and governed "
        "mock-only boundaries are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
