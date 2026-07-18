# ruff: noqa: E402
#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.factory_control_plane.common import ControlPlaneError, PRODUCT_ID, load_json_object
from tools.factory_control_plane.failures import FailureClass, consumes_repair_budget
from tools.factory_control_plane.manifest import load_manifest
from tools.factory_control_plane.policy import StandingPolicy


REQUIRED_FILES = [
    "tools/factory_control_plane/__init__.py",
    "tools/factory_control_plane/common.py",
    "tools/factory_control_plane/lifecycle.py",
    "tools/factory_control_plane/manifest.py",
    "tools/factory_control_plane/policy.py",
    "tools/factory_control_plane/executor.py",
    "tools/factory_control_plane/state.py",
    "tools/factory_control_plane/evidence.py",
    "tools/factory_control_plane/failures.py",
    "tools/factory_control_plane/adapters.py",
    "tools/factory_control_plane/engine.py",
    "tools/factory_control_plane/worker.py",
    "tools/factory_control_plane/cli.py",
    "config/control_plane/standing_policy.json",
    "config/control_plane/campaigns/control_plane_self_test.json",
    "schemas/control_plane/campaign_manifest.schema.json",
    "schemas/control_plane/policy_decision.schema.json",
    "schemas/control_plane/activity_result.schema.json",
    "docs/control_plane/README.md",
    "docs/adr/ADR-0067-repository-owned-autonomous-control-plane.md",
    "scripts/validate_autonomous_control_plane_bootstrap.py",
    "bin/upi-app-factory-control-plane",
]

FORBIDDEN_LABEL = "-".join(("autonomous", "control", "plane", "bootstrap", "v1"))
HUMAN_REQUIRED = {
    "production_deployment",
    "public_release",
    "create_tag",
    "real_payment_rail_access",
    "real_customer_data_access",
    "policy_exception",
    "destructive_migration",
    "certification_claim",
}
PROHIBITED = {
    "force_push_main",
    "bypass_required_checks",
    "disable_governance",
    "commit_secret",
    "delete_evidence",
    "live_payment_transaction",
}
REQUIRED_FAILURE_CLASSES = {
    "PRODUCT_DEFECT",
    "TEST_DEFECT",
    "MISSING_PREREQUISITE",
    "NON_HERMETIC_TEST",
    "DETERMINISTIC_RUNTIME_NOISE",
    "BASELINE_DEFECT",
    "CONTROLLER_DEFECT",
    "POLICY_DENIAL",
    "EVIDENCE_INTEGRITY_FAILURE",
}


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if path.suffix == ".json" and path.is_file():
            try:
                load_json_object(path)
            except Exception as exc:
                errors.append(f"invalid json {relative}: {exc}")
    if PRODUCT_ID != "upi_app_factory":
        errors.append("canonical product id marker mismatch")
    try:
        manifest = load_manifest(
            ROOT / "config/control_plane/campaigns/control_plane_self_test.json",
            ROOT,
        )
        if manifest.campaign_id != "control_plane_self_test":
            errors.append("self-test campaign id mismatch")
        if not manifest.validation_controls.trusted_prerequisites:
            errors.append("self-test manifest must declare trusted prerequisites")
        if not manifest.validation_controls.deterministic_runtime_noise:
            errors.append("self-test manifest must declare runtime noise")
    except Exception as exc:
        errors.append(f"self-test manifest loader failed: {exc}")
    actual_failure_classes = {item.value for item in FailureClass}
    if not REQUIRED_FAILURE_CLASSES <= actual_failure_classes:
        errors.append("failure class vocabulary is incomplete")
    if not consumes_repair_budget(FailureClass.PRODUCT_DEFECT):
        errors.append("product defects must consume repair budget")
    for failure_class in FailureClass:
        if (
            failure_class is not FailureClass.PRODUCT_DEFECT
            and consumes_repair_budget(failure_class)
        ):
            errors.append(f"non-product failure consumes repair budget: {failure_class.value}")
    try:
        policy = StandingPolicy(ROOT / "config/control_plane/standing_policy.json")
        automatic = set(_as_list(policy.raw.get("automatic_actions")))
        human = set(_as_list(policy.raw.get("human_required_actions")))
        prohibited = set(_as_list(policy.raw.get("prohibited_actions")))
        if policy.raw.get("default") != "deny":
            errors.append("standing policy must default deny")
        if not HUMAN_REQUIRED <= human:
            errors.append("standing policy misses human-required actions")
        if not PROHIBITED <= prohibited:
            errors.append("standing policy misses prohibited actions")
        forbidden_auto = (HUMAN_REQUIRED | PROHIBITED) & automatic
        if forbidden_auto:
            errors.append(
                "production/release/certification authorization detected: "
                f"{sorted(forbidden_auto)}"
            )
        if policy.evaluate("unknown_action", "LOW").outcome != "deny":
            errors.append("unknown action is not denied")
        if policy.evaluate("certification_claim", "LOW").outcome != "pause":
            errors.append("certification statement action must be human-gated")
        if policy.evaluate("live_payment_transaction", "LOW").outcome != "deny":
            errors.append("live payment transaction must be denied")
    except Exception as exc:
        errors.append(f"standing policy inspection failed: {exc}")
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if (
            path.is_file()
            and FORBIDDEN_LABEL in path.read_text(encoding="utf-8")
        ):
            errors.append(f"forbidden product label found in {relative}")
    result: dict[str, Any] = {
        "status": "PASS" if not errors else "FAIL",
        "passed": not errors,
        "errors": errors,
        "checked_files": REQUIRED_FILES,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ControlPlaneError("expected list")
    return [str(item) for item in value]


if __name__ == "__main__":
    raise SystemExit(main())
