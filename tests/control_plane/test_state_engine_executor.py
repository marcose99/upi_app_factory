from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.executor import CapabilityExecutor
from tools.factory_control_plane.failures import FailureClass, consumes_repair_budget
from tools.factory_control_plane.manifest import load_manifest
from tools.factory_control_plane.state import StateStore


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "config/control_plane/campaigns/control_plane_self_test.json"
POLICY = ROOT / "config/control_plane/standing_policy.json"


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SELF_TEST.read_text(encoding="utf-8")))


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sqlite_persistence_and_idempotent_replay(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        first = engine.run(SELF_TEST)
        assert first["status"] == "closed"
        assert not (ROOT / "var/control_plane_self_test").exists()
    finally:
        engine.close()
    reopened = StateStore(state_root / "control_plane.sqlite3")
    try:
        assert reopened.summary("control_plane_self_test")["state"] == "CLOSED"
        assert reopened.summary("control_plane_self_test")["completed_activities"] == 3
    finally:
        reopened.close()
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        second = engine.run(SELF_TEST)
        assert second["status"] == "closed"
        assert second["summary"]["completed_activities"] == 3
    finally:
        engine.close()


def test_manifest_and_changed_activity_drift_rejected(tmp_path: Path) -> None:
    payload = _payload()
    manifest_path = _write(tmp_path, payload)
    state_root = tmp_path / "state"
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        assert engine.run(manifest_path)["status"] == "closed"
    finally:
        engine.close()
    payload["activities"][0]["timeout_seconds"] = 31
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        with pytest.raises(ControlPlaneError, match="manifest drift"):
            engine.run(manifest_path)
    finally:
        engine.close()


def test_changed_inputs_for_existing_activity_fail_closed(tmp_path: Path) -> None:
    manifest = load_manifest(SELF_TEST, ROOT)
    store = StateStore(tmp_path / "state.sqlite3")
    try:
        store.create_or_load_campaign(manifest, manifest.baseline)
        activity = manifest.activities[0]
        store.record_activity("control_plane_self_test", activity, "completed", {"ok": True})
        payload = _payload()
        payload["activities"][0]["timeout_seconds"] = 31
        changed = load_manifest(_write(tmp_path, payload), ROOT)
        with pytest.raises(ControlPlaneError, match="changed inputs"):
            store.activity_status("control_plane_self_test", changed.activities[0])
    finally:
        store.close()


def test_capability_executor_restrictions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    manifest = load_manifest(_write(tmp_path, payload), ROOT)
    executor = CapabilityExecutor(ROOT)
    bad_exe = manifest.activities[0]
    object.__setattr__(bad_exe, "argv", ("sh", "-c", "true"))
    with pytest.raises(ControlPlaneError, match="allowlisted"):
        executor.run(bad_exe)
    bad_cwd = manifest.activities[0]
    object.__setattr__(bad_cwd, "argv", ("python3", "-c", "print('ok')"))
    object.__setattr__(bad_cwd, "cwd", "../")
    with pytest.raises(ControlPlaneError, match="escapes"):
        executor.run(bad_cwd)
    monkeypatch.setenv("CONTROL_PLANE_TEST_ALLOWED", "kept")
    ok = manifest.activities[1]
    object.__setattr__(
        ok,
        "argv",
        ("python3", "-c", "import os; print(os.getenv('CONTROL_PLANE_TEST_ALLOWED'))"),
    )
    object.__setattr__(ok, "environment_allowlist", ("CONTROL_PLANE_TEST_ALLOWED",))
    result = executor.run(ok)
    assert result.returncode == 0
    assert "kept" in result.stdout
    assert result.stderr == ""


def test_failed_activity_incident_without_state_rollback(tmp_path: Path) -> None:
    payload = _payload()
    payload["activities"][1]["argv"] = ["python3", "-c", "raise SystemExit(4)"]
    manifest_path = _write(tmp_path, payload)
    engine = ControlPlaneEngine(ROOT, tmp_path / "state", POLICY)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        summary = engine.status("control_plane_self_test")
        assert summary["state"] == "ENGINEERING"
        assert summary["incidents"] == 1
        assert result["failure_class"] == FailureClass.BASELINE_DEFECT.value
    finally:
        engine.close()


def test_failure_classification_repair_budget() -> None:
    assert consumes_repair_budget(FailureClass.PRODUCT_DEFECT)
    assert not consumes_repair_budget(FailureClass.POLICY_DENIAL)
    assert not consumes_repair_budget(FailureClass.TEST_DEFECT)
    assert not consumes_repair_budget(FailureClass.BASELINE_DEFECT)
    assert os.name


def _classification_manifest(
    tmp_path: Path,
    script: str,
    prerequisites: list[dict[str, Any]] | None = None,
    noise: list[dict[str, Any]] | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": "classification_case",
        "metadata": {"product": "UPI App Factory", "product_id": "upi_app_factory"},
        "baseline": "BASELINE_COMMIT",
        "objective": "Exercise validation classification.",
        "scope": {"allowed_write_paths": ["runtime"]},
        "budgets": {"engineering_repairs": 1, "activity_seconds": 60},
        "approvals": {"human": []},
        "validation_controls": {
            "trusted_prerequisites": prerequisites or [],
            "deterministic_runtime_noise": noise or [],
        },
        "activities": [
            {
                "id": "observe",
                "action": "run_tests",
                "kind": "verification",
                "risk": "LOW",
                "argv": ["python3", "-c", script],
                "dependencies": [],
                "target_state": "OFFLINE_VALIDATED",
                "timeout_seconds": 30,
                "cwd": ".",
                "environment_allowlist": [],
                "allowed_write_paths": [],
            }
        ],
    }
    return _write(tmp_path, payload)


def test_identical_baseline_failure_does_not_consume_repair_budget(tmp_path: Path) -> None:
    manifest_path = _classification_manifest(tmp_path, "raise SystemExit(7)")
    engine = ControlPlaneEngine(tmp_path, tmp_path / "state", POLICY)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.BASELINE_DEFECT.value
        assert result["consumes_repair_budget"] is False
    finally:
        engine.close()


def test_candidate_attributable_product_defect_consumes_repair_budget(tmp_path: Path) -> None:
    script = (
        "import os; "
        "raise SystemExit(0 if os.environ['UPI_APP_FACTORY_OBSERVATION_SUBJECT'] "
        "== 'baseline' else 5)"
    )
    manifest_path = _classification_manifest(tmp_path, script)
    engine = ControlPlaneEngine(tmp_path, tmp_path / "state", POLICY)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.PRODUCT_DEFECT.value
        assert result["consumes_repair_budget"] is True
    finally:
        engine.close()


def test_missing_prerequisite_and_runtime_noise_are_control_plane_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "runtime/noise").mkdir(parents=True)
    manifest_path = _classification_manifest(
        tmp_path,
        "raise SystemExit(0)",
        prerequisites=[
            {
                "id": "missing_validation_fixture",
                "kind": "file",
                "path": "runtime/missing.txt",
                "hydrate": False,
            }
        ],
        noise=[
            {
                "id": "ignored_runtime_noise",
                "kind": "directory",
                "path": "runtime/noise",
            }
        ],
    )
    engine = ControlPlaneEngine(tmp_path, tmp_path / "state", POLICY)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.MISSING_PREREQUISITE.value
        assert not (tmp_path / "runtime/noise").exists()
        evidence = tmp_path / "state/evidence/classification_case/control/reconcile.json"
        assert json.loads(evidence.read_text(encoding="utf-8"))["runtime_noise"][0][
            "removed"
        ]
    finally:
        engine.close()
