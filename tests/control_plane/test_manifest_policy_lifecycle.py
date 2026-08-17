from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.lifecycle import LifecycleState, advance
from tools.factory_control_plane.manifest import load_manifest
from tools.factory_control_plane.policy import StandingPolicy


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "config/control_plane/campaigns/control_plane_self_test.json"
POLICY = ROOT / "config/control_plane/standing_policy.json"


def _manifest_payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SELF_TEST.read_text(encoding="utf-8")))


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_manifest_parses_self_test() -> None:
    manifest = load_manifest(SELF_TEST, ROOT)
    assert manifest.schema_version == 1
    assert manifest.campaign_id == "control_plane_self_test"
    assert manifest.activities[1].kind == "verification"


def test_cycle_unknown_duplicate_and_out_of_scope_fail(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["activities"][0]["dependencies"] = ["cleanup_self_test_file"]
    with pytest.raises(ControlPlaneError, match="cycle"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["activities"][1]["dependencies"] = ["missing"]
    with pytest.raises(ControlPlaneError, match="unknown dependency"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["activities"][1]["id"] = "create_self_test_file"
    with pytest.raises(ControlPlaneError, match="duplicate"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["activities"][0]["allowed_write_paths"] = ["README.md"]
    with pytest.raises(ControlPlaneError, match="outside manifest scope"):
        load_manifest(_write(tmp_path, payload), ROOT)


def test_unknown_fields_budget_and_non_monotonic_targets_fail(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["unexpected"] = True
    with pytest.raises(ControlPlaneError, match="unknown fields"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["budgets"]["engineering_repairs"] = -1
    with pytest.raises(ControlPlaneError, match="budget"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["activities"][1]["target_state"] = "WORKSPACE_READY"
    with pytest.raises(ControlPlaneError, match="monotonic"):
        load_manifest(_write(tmp_path, payload), ROOT)


def test_verification_cannot_declare_writes(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["activities"][1]["allowed_write_paths"] = ["var/control_plane_self_test"]
    with pytest.raises(ControlPlaneError, match="verification"):
        load_manifest(_write(tmp_path, payload), ROOT)


@pytest.mark.parametrize("path", [".git", "config", "README.md", "var"])
def test_runtime_noise_must_be_inside_campaign_scope(tmp_path: Path, path: str) -> None:
    payload = _manifest_payload()
    payload["validation_controls"]["deterministic_runtime_noise"][0]["path"] = path
    with pytest.raises(ControlPlaneError, match="outside manifest scope"):
        load_manifest(_write(tmp_path, payload), ROOT)


def test_lifecycle_monotonic_and_terminal() -> None:
    assert (
        advance(LifecycleState.NEW, LifecycleState.INTAKE_VALIDATED)
        is LifecycleState.INTAKE_VALIDATED
    )
    with pytest.raises(ControlPlaneError, match="backward"):
        advance(LifecycleState.ENGINEERING, LifecycleState.WORKSPACE_READY)
    with pytest.raises(ControlPlaneError, match="terminal"):
        advance(LifecycleState.CLOSED, LifecycleState.CLEANED)


def test_policy_allow_pause_deny_and_deterministic_ids() -> None:
    policy = StandingPolicy(POLICY)
    allowed = policy.evaluate("run_tests", "MODERATE")
    assert allowed.outcome == "allow"
    assert allowed == policy.evaluate("run_tests", "MODERATE")
    paused = policy.evaluate("production_deployment", "LOW")
    assert paused.outcome == "pause"
    assert paused.human_required
    assert policy.evaluate("live_payment_transaction", "LOW").outcome == "deny"
    assert policy.evaluate("not_in_policy", "LOW").outcome == "deny"
    assert policy.evaluate("run_tests", "HIGH").outcome == "deny"


def test_policy_membership_overlap_fails_at_production_load(tmp_path: Path) -> None:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    payload["automatic_actions"].append("production_deployment")
    path = _write(tmp_path, payload)
    with pytest.raises(ControlPlaneError, match="disjoint"):
        StandingPolicy(path)


def test_payload_copy_keeps_type_checking_honest() -> None:
    payload = _manifest_payload()
    cloned = copy.deepcopy(payload)
    assert cloned == payload


@pytest.mark.parametrize("target", ["PR_OPEN", "MERGED", "POSTMERGE_ACCEPTED"])
def test_automatic_capability_cannot_claim_protected_state(
    tmp_path: Path, target: str
) -> None:
    payload = _manifest_payload()
    payload["activities"][-1]["target_state"] = target
    with pytest.raises(ControlPlaneError, match="not authorized for target state"):
        load_manifest(_write(tmp_path, payload), ROOT)


def test_automatic_capability_cannot_borrow_another_actions_transition(
    tmp_path: Path,
) -> None:
    payload = _manifest_payload()
    payload["activities"][0]["action"] = "verify_evidence"
    with pytest.raises(ControlPlaneError, match="not authorized for target state"):
        load_manifest(_write(tmp_path, payload), ROOT)


@pytest.mark.parametrize("identifier", ["../escape", "a/b", ".hidden", "name\nnext"])
def test_manifest_rejects_path_capable_identifiers(
    tmp_path: Path, identifier: str
) -> None:
    payload = _manifest_payload()
    payload["campaign_id"] = identifier
    with pytest.raises(ControlPlaneError, match="conservative"):
        load_manifest(_write(tmp_path, payload), ROOT)

    payload = _manifest_payload()
    payload["activities"][0]["id"] = identifier
    with pytest.raises(ControlPlaneError, match="conservative"):
        load_manifest(_write(tmp_path, payload), ROOT)
