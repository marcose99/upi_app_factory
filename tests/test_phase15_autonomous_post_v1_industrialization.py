from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_phase15_autonomous_post_v1_industrialization.py"
VALIDATOR = ROOT / "scripts" / "validate_phase15_autonomous_post_v1_industrialization.py"
AUDIT = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase15" / "autonomous_post_v1_industrialization_audit.json"
FRESH_REPLAY = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase15" / "tagged_v1_fresh_clone_replay_result.json"


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return cast(dict[str, object], data)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def test_phase15_runner_generates_temporary_audit(tmp_path: Path) -> None:
    audit_path = tmp_path / "phase15_audit.json"
    completed = run_command([sys.executable, str(RUNNER), "--audit-out", str(audit_path)])
    assert completed.returncode == 0, completed.stderr
    audit = load_json(audit_path)
    assert audit["schema_version"] == "autonomous-post-v1-industrialization-batch.v1"
    assert audit["phase"] == "15A-F"
    assert audit["governed_self_evolution_enabled"] is True
    assert audit["validators_are_read_only"] is True
    assert audit["tests_use_temporary_audit_outputs"] is True
    assert audit["factory_does_not_self_certify"] is True
    assert audit["official_certification_claimed"] is False
    assert audit["batch_phases"] == ["15A", "15B", "15C", "15D", "15E", "15F"]


def test_phase15_runner_readonly_gates_are_declared() -> None:
    audit = load_json(AUDIT)
    gate_specs = audit["read_only_gate_specs"]
    assert isinstance(gate_specs, list)
    assert gate_specs
    for gate in gate_specs:
        assert isinstance(gate, dict)
        assert gate["read_only"] is True
        assert gate["parallel_safe"] is True
        assert "mutation_profile" in gate


def test_phase15_fresh_clone_replay_result_is_recorded() -> None:
    replay = load_json(FRESH_REPLAY)
    assert replay["status"] == "PASS"
    assert replay["base_tag_replayed"] == "v0.14.23-operator-autonomy-dashboard-v1-readiness-pack"
    assert replay["fresh_clone_replay_performed"] is True
    assert replay["phase13g_guardrail_replayed"] is True
    assert replay["phase14yz_readiness_validator_replayed"] is True
    assert replay["phase14yz_targeted_tests_replayed"] is True
    assert replay["official_certification_claimed"] is False


def test_phase15_validator_accepts_committed_artifacts() -> None:
    completed = run_command([sys.executable, str(VALIDATOR)])
    assert completed.returncode == 0, completed.stderr
    assert "Phase 15 autonomous post-v1 industrialization artifacts validated." in completed.stdout


def test_phase15_policy_preserves_human_gates() -> None:
    policy = load_json(ROOT / "policies" / "phase15_autonomous_post_v1_industrialization_policy.json")
    gates = policy["human_approval_required_for"]
    assert isinstance(gates, list)
    for required in [
        "merge",
        "tag",
        "push",
        "release",
        "promotion",
        "live_provider_calls",
        "destructive_operations",
        "official_certification_claims",
        "unknown_failure_classes",
        "risky_generated_application_changes",
    ]:
        assert required in gates
