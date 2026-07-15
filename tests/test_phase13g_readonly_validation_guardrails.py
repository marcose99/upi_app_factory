from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID
AUDIT_PATH = WORKSPACE / "lifecycle_artifacts" / "phase13g" / "readonly_validation_audit.json"
PORTAL_PATH = WORKSPACE / "audit_portal" / "factory_readonly_validation_drift_guardrails_portal.html"

ALLOWED_LEGACY_TRACKED_DRIFT = [
    "workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_operator_handover_closure_portal.html",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13f/operator_handover_audit.json",
]


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def tracked_changed() -> list[str]:
    completed = run_command(["git", "status", "--porcelain=v1"], check=True)
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip() or line.startswith("??"):
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return sorted(set(paths))


def unexpected_generated_drift() -> list[str]:
    return [
        path
        for path in tracked_changed()
        if path.startswith("workspace/factory_generated/")
        and path not in ALLOWED_LEGACY_TRACKED_DRIFT
        and "phase13g" not in path
    ]


def test_phase13g_audit_passes_and_documents_policy() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["phase"] == "Phase 13G"
    assert audit["passed"] is True
    assert audit["readonly_validation_policy"]["mutation_allowed_during_validation"] is False
    assert audit["readonly_validation_policy"]["legacy_drift_handling"] == "detect_restore_and_report"
    assert audit["guardrail_result"]["all_commands_succeeded"] is True


def test_phase13g_validator_is_safe_with_legacy_drift_guardrail(
    tmp_path: Path,
) -> None:
    before_unexpected = unexpected_generated_drift()
    snapshot = tmp_path / "phase13g_clean_clone"
    head = run_command(["git", "rev-parse", "HEAD"], check=True).stdout.strip()

    subprocess.run(
        [
            "git",
            "clone",
            "--no-hardlinks",
            "--quiet",
            str(ROOT),
            str(snapshot),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "--detach", head],
        cwd=snapshot,
        text=True,
        capture_output=True,
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase13g_readonly_validation_guardrails.py",
        ],
        cwd=snapshot,
        text=True,
        capture_output=True,
        check=True,
    )
    assert '"passed": true' in completed.stdout
    assert unexpected_generated_drift() == before_unexpected


def test_phase13g_portal_exists_and_is_deterministic_operator_evidence() -> None:
    html = PORTAL_PATH.read_text(encoding="utf-8")
    assert "Phase 13G: Read-only Validation Drift Guardrails" in html
    assert "Drift events detected/restored" in html
    assert "Truth boundary" in html
    assert "generated_at" not in html.lower()
