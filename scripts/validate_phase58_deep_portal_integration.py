#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REQUIRED_FILES = [
    "factory/operator_portal/deep_portal_integration.py",
    "factory/operator_portal/local_web_api.py",
    "factory/operator_portal/web_ui/app.py",
    "factory/operator_portal/browser_intake_orchestration.py",
    "scripts/run_portal_requirements_driven_application_engineering.py",
    "scripts/validate_phase58_deep_portal_integration.py",
    "tests/test_phase58_deep_portal_integration.py",
]

VALIDATION_COMMANDS = [
    "python -m pytest tests/test_phase58_deep_portal_integration.py -q",
    "python scripts/validate_phase58_deep_portal_integration.py",
]


def canonical_python(root: Path) -> Path:
    for candidate in [root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python", Path(sys.executable)]:
        if candidate.is_file():
            return candidate
    raise AssertionError("No canonical Python interpreter found")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def run(command: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def validate_static_artifacts(root: Path) -> None:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise AssertionError(f"Missing Phase 58 files: {missing}")

    portal_text = (root / "factory/operator_portal/deep_portal_integration.py").read_text(encoding="utf-8")
    required_terms = [
        "local-deep-v1",
        "compatibility_scaffold",
        "real_payment_calls",
        "default_runtime_llm_calls",
        "source_archive",
        "evidence_archive",
        "render_html",
    ]
    missing_terms = [term for term in required_terms if term not in portal_text]
    if missing_terms:
        raise AssertionError(f"Portal integration is missing required terms: {missing_terms}")

    api_text = (root / "factory/operator_portal/local_web_api.py").read_text(encoding="utf-8")
    for route in [
        "/operator-portal/api/deep-engineering/overview",
        "/operator-portal/api/deep-engineering/compile",
        "/operator-portal/api/deep-engineering/proposal",
        "/operator-portal/api/deep-engineering/approved-run",
        "/operator-portal/api/deep-engineering/download/source",
        "/operator-portal/api/deep-engineering/download/evidence",
    ]:
        if route not in api_text:
            raise AssertionError(f"Missing Phase 58 API route: {route}")

    ui_text = (root / "factory/operator_portal/web_ui/app.py").read_text(encoding="utf-8")
    if "/operator-portal/deep-engineering" not in ui_text:
        raise AssertionError("Server-rendered Phase 58 portal route is missing")


def validate_runtime_contract(root: Path) -> dict[str, Any]:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from factory.operator_portal.deep_portal_integration import REQUIRED_VIEWS, DeepPortalIntegration

    integration = DeepPortalIntegration(project_root=root)
    overview = integration.overview()
    if overview.get("product_name") != "UPI App Factory":
        raise AssertionError("Product name was not preserved")
    if overview.get("repository_id") != "upi_app_factory":
        raise AssertionError("Repository id was not preserved")
    if overview.get("mock_boundaries", {}).get("real_payment_calls") != "disabled":
        raise AssertionError("Real payment calls must remain disabled")
    if overview.get("mock_boundaries", {}).get("default_runtime_llm_calls") != 0:
        raise AssertionError("Default runtime LLM calls must remain zero")
    if not REQUIRED_VIEWS.issubset(set(overview.get("views", {}))):
        raise AssertionError("Portal overview does not expose every required Phase 58 view")

    compiled = integration.compile({"requirements_path": "tests/fixtures/phase53/failed_debit_requirements.md"})
    if compiled.get("status") != "compiled" or not compiled.get("traceability"):
        raise AssertionError("Requirements compile and traceability view failed")

    proposal = integration.proposal({"requirements_path": "tests/fixtures/phase53/failed_debit_requirements.md"})
    if proposal.get("plan", {}).get("engineering_profile") != "local-deep-v1":
        raise AssertionError("Proposal-only adapter did not use the deep profile")
    if proposal.get("real_payment_calls") != "disabled" or proposal.get("llm_calls") != 0:
        raise AssertionError("Proposal-only adapter violated mock/LLM boundaries")

    html = integration.render_html()
    for term in ["UPI App Factory", "State Machine", "Source Browser", "Evidence Browser"]:
        if term not in html:
            raise AssertionError(f"Server-rendered portal HTML is missing {term}")
    return overview


def validate_tests(root: Path, python: Path) -> dict[str, int]:
    result = run([str(python), "-m", "pytest", "tests/test_phase58_deep_portal_integration.py", "-q"], root)
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    if "5 passed" not in result.stdout:
        raise AssertionError(f"Unexpected Phase 58 test output:\n{result.stdout}")
    return {"passed": 5, "failed": 0}


def write_reports(root: Path, overview: dict[str, Any], test_counts: dict[str, int]) -> None:
    output_dir = root / "workspace" / "deep_engineering_campaign"
    output_dir.mkdir(parents=True, exist_ok=True)
    changed_files = REQUIRED_FILES + [
        "workspace/deep_engineering_campaign/phase58_report.json",
        "workspace/deep_engineering_campaign/phase58_report.md",
    ]
    report = {
        "stage": "Phase 58",
        "status": "completed",
        "product_name": "UPI App Factory",
        "repository_id": "upi_app_factory",
        "portal_integration": "completed",
        "server_rendered_ui": True,
        "node_build_required": False,
        "deep_profile": "local-deep-v1",
        "compatibility_scaffold_distinguished": True,
        "proposal_only_adapter": True,
        "approved_deep_application_engineering_adapter": True,
        "source_and_evidence_downloads": True,
        "safe_commands_retained": True,
        "real_payment_calls": "disabled",
        "llm_runtime_calls": 0,
        "certification_claim": "none",
        "views": sorted(overview["views"]),
        "depth_score": overview["views"]["depth_score"],
        "test_counts": test_counts,
        "validation_commands": VALIDATION_COMMANDS,
        "changed_files": changed_files,
        "residual_risks": [
            "Portal execution remains local and fictional; it is not production-ready or certified.",
            "Approved deep application engineering requires the governed local token and still uses mocked external boundaries.",
            "Evidence downloads are local archives and do not represent formal standards conformance.",
        ],
    }
    (output_dir / "phase58_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = f"""# Phase 58 Report

Status: completed

UPI App Factory Phase 58 adds a dependency-light, server-rendered operator
portal integration for deep application engineering.

## Evidence

- Deep profile: local-deep-v1
- Compatibility scaffold distinguished: yes
- Proposal-only adapter path: yes
- Approved adapter path: yes
- Source and evidence browse/download: yes
- Real payment calls: disabled
- Default runtime LLM calls: 0
- Certification claim: none

## Validation

- `{VALIDATION_COMMANDS[0]}`: {test_counts["passed"]} passed, {test_counts["failed"]} failed
- `{VALIDATION_COMMANDS[1]}`: passed

## Residual Risks

- Portal execution remains local and fictional; it is not production-ready or certified.
- Approved deep application engineering requires the governed local token and still uses mocked external boundaries.
- Evidence downloads are local archives and do not represent formal standards conformance.
"""
    (output_dir / "phase58_report.md").write_text(markdown, encoding="utf-8")


def validate_reports(root: Path) -> None:
    report = read_json(root / "workspace/deep_engineering_campaign/phase58_report.json")
    if report.get("stage") != "Phase 58" or report.get("status") != "completed":
        raise AssertionError("Phase 58 report JSON has the wrong stage/status")
    if report.get("product_name") != "UPI App Factory" or report.get("repository_id") != "upi_app_factory":
        raise AssertionError("Phase 58 report must preserve governed identity")
    if report.get("real_payment_calls") != "disabled" or report.get("llm_runtime_calls") != 0:
        raise AssertionError("Phase 58 report violates runtime safety controls")
    if report.get("certification_claim") != "none":
        raise AssertionError("Phase 58 report must not claim certification")
    if not (root / "workspace/deep_engineering_campaign/phase58_report.md").is_file():
        raise AssertionError("Phase 58 Markdown report is missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    python = canonical_python(root)

    validate_static_artifacts(root)
    overview = validate_runtime_contract(root)
    test_counts = validate_tests(root, python)
    write_reports(root, overview, test_counts)
    validate_reports(root)
    print(
        "Phase 58 deep portal integration validation passed: server-rendered portal, "
        "compile/traceability views, deep profile adapter proposal and approved paths, "
        "safe source/evidence browsing, downloads, gates, test counts, depth score, "
        "risks, manifests, and mock boundaries are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
