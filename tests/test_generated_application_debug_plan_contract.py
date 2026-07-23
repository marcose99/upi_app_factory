from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from factory.debugging import validate_debug_plan
from factory.debugging.debug_plan import canonical_plan_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_TEXT = "Failed debit and beneficiary no-credit support with mock-safe deterministic operations. " * 3


def _generate(tmp_path: Path, app_id: str) -> Path:
    output_root = (
        Path(os.environ.get("UPI_APP_FACTORY_DEBUG_PLAN_TEST_OUTPUT_ROOT", str(tmp_path / "generated")))
        / app_id
        / "generated_application"
    )
    requirements = tmp_path / f"{app_id}.md"
    requirements.write_text(REQUIREMENTS_TEXT + app_id + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/run_portal_requirements_driven_application_engineering.py"),
            "--requirements",
            str(requirements),
            "--app-id",
            app_id,
            "--output-root",
            str(output_root),
            "--evidence-root",
            str(output_root.parent / "evidence"),
            "--approval-token",
            "APPROVE_PORTAL_APPLICATION_ENGINEERING",
            "--mock-safe",
            "--replace-existing",
        ],
        cwd=Path("/tmp"),
        env={**os.environ, "UPI_APP_FACTORY_ROOT": str(PROJECT_ROOT), "UPI_APP_FACTORY_WORKSPACE_ROOT": str(output_root.parents[2]), "REAL_PAYMENT_CALLS": "disabled", "FACTORY_LLM_ENABLED": "0"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return output_root


def test_generated_applications_include_hash_bound_debug_plan(tmp_path: Path) -> None:
    roots = [_generate(tmp_path, "upi_failed_debit_no_credit"), _generate(tmp_path, "upi_debug_plan_probe")]
    for root in roots:
        assert (root / "docs/DEBUG_PLAN.md").is_file()
        plan_path = root / "evidence/debug_plan.json"
        assert plan_path.is_file()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["app_id"] == root.parents[0].name
        assert {"method": "POST", "path": "/v1/disputes"} in plan["routes"]
        assert validate_debug_plan(plan_path, app_root=root).valid
        manifest = json.loads((root / "generation_manifest.json").read_text(encoding="utf-8"))
        paths = {item.get("path") or item.get("relative_path") for item in manifest["files"]}
        assert "docs/DEBUG_PLAN.md" in paths
        assert "evidence/debug_plan.json" in paths


def test_generated_debug_plan_rejects_wrong_identity(tmp_path: Path) -> None:
    root = _generate(tmp_path, "upi_debug_plan_probe")
    plan_path = root / "evidence/debug_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["requirements_sha256"] = "0" * 64
    plan["plan_sha256"] = canonical_plan_sha256(plan)
    tampered = tmp_path / "wrong_identity.json"
    tampered.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "requirements identity drift" in validate_debug_plan(tampered, app_root=root).errors

    plan["requirements_sha256"] = json.loads(plan_path.read_text(encoding="utf-8"))["requirements_sha256"]
    plan["app_id"] = "wrong_app"
    plan["plan_sha256"] = canonical_plan_sha256(plan)
    wrong_app = tmp_path / "wrong_app.json"
    wrong_app.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "wrong app identity" in validate_debug_plan(wrong_app, app_root=root).errors
