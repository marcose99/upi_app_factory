from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from factory.debugging import build_factory_debug_plan, validate_debug_plan
from factory.debugging.debug_plan import canonical_plan_sha256
from factory.operator_portal.browser_intake_orchestration import VALID_TRANSITIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_factory_debug_plan_cli_and_contract(tmp_path: Path) -> None:
    json_out = tmp_path / "factory_debug_plan.json"
    text_out = tmp_path / "factory_debug_plan.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/build_factory_debug_plan.py"),
            "--project-root",
            str(PROJECT_ROOT),
            "--json-out",
            str(json_out),
            "--text-out",
            str(text_out),
        ],
        cwd=Path("/tmp"),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(json_out.read_text(encoding="utf-8"))
    assert plan["schema_version"] == "upi-app-factory.debug-plan.v1"
    assert plan["plan_kind"] == "factory"
    assert {"method": "GET", "path": "/operator-portal/api/debug-plan/factory"} in plan["routes"]
    assert {"method": "GET", "path": "/operator-portal/api/documentation/factory"} in plan["routes"]
    observed = {
        (transition["from"], transition["to"])
        for machine in plan["state_machines"]
        for transition in machine["transitions"]
    }
    expected = {(source, target) for source, targets in VALID_TRANSITIONS.items() for target in targets}
    assert expected <= observed
    result = validate_debug_plan(json_out, project_root=PROJECT_ROOT)
    assert result.valid, result.errors
    assert text_out.read_text(encoding="utf-8").startswith("# Debug Plan")


def test_factory_debug_plan_negative_drift_cases(tmp_path: Path) -> None:
    plan = build_factory_debug_plan(PROJECT_ROOT)
    base = tmp_path / "plan.json"
    base.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert validate_debug_plan(base, project_root=PROJECT_ROOT).valid

    stale = dict(plan)
    stale["app_id"] = "tampered"
    stale_path = tmp_path / "stale.json"
    stale_path.write_text(json.dumps(stale, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "plan_sha256 drift" in validate_debug_plan(stale_path, project_root=PROJECT_ROOT).errors

    missing_route = dict(plan)
    missing_route["routes"] = plan["routes"][1:]
    missing_route["plan_sha256"] = "0" * 64
    missing_route["plan_sha256"] = canonical_plan_sha256(missing_route)
    missing_route_path = tmp_path / "missing_route.json"
    missing_route_path.write_text(json.dumps(missing_route, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert any("route inventory drift" in error for error in validate_debug_plan(missing_route_path, project_root=PROJECT_ROOT).errors)

    missing_transition = dict(plan)
    missing_transition["state_machines"] = [{"name": "browser_intake_run", "transitions": []}]
    missing_transition["plan_sha256"] = canonical_plan_sha256(missing_transition)
    missing_transition_path = tmp_path / "missing_transition.json"
    missing_transition_path.write_text(json.dumps(missing_transition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "state-machine inventory drift" in validate_debug_plan(missing_transition_path, project_root=PROJECT_ROOT).errors

    unsafe = dict(plan)
    unsafe["commands"] = [{"name": "bad", "argv": ["sh", "-c", "echo bad; rm -rf /"], "expected_signals": [], "failure_signals": []}]
    unsafe["plan_sha256"] = canonical_plan_sha256(unsafe)
    unsafe_path = tmp_path / "unsafe.json"
    unsafe_path.write_text(json.dumps(unsafe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "unsafe command argument detected" in validate_debug_plan(unsafe_path, project_root=PROJECT_ROOT).errors

    leaked = dict(plan)
    leaked["notes"] = "approval_token=APPROVE_PORTAL_APPLICATION_ENGINEERING"
    leaked["plan_sha256"] = canonical_plan_sha256(leaked)
    leaked_path = tmp_path / "leaked.json"
    leaked_path.write_text(json.dumps(leaked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "secret-like material leaked into plan" in validate_debug_plan(leaked_path, project_root=PROJECT_ROOT).errors
