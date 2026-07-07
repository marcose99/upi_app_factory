#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DOC = ROOT / "docs" / "phase15" / "autonomous_post_v1_industrialization_batch.md"
POLICY = ROOT / "policies" / "phase15_autonomous_post_v1_industrialization_policy.json"
RUNNER = ROOT / "scripts" / "run_phase15_autonomous_post_v1_industrialization.py"
VALIDATOR = ROOT / "scripts" / "validate_phase15_autonomous_post_v1_industrialization.py"
TESTS = ROOT / "tests" / "test_phase15_autonomous_post_v1_industrialization.py"
AUDIT = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase15" / "autonomous_post_v1_industrialization_audit.json"
FRESH_REPLAY = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase15" / "tagged_v1_fresh_clone_replay_result.json"


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"Expected JSON object in {path}")
    return cast(dict[str, object], data)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_bool(data: dict[str, object], key: str, expected: bool) -> None:
    require(data.get(key) is expected, f"{key} must be {expected}")


def main() -> int:
    for path in [DOC, POLICY, RUNNER, VALIDATOR, TESTS, AUDIT, FRESH_REPLAY]:
        require(path.exists(), f"Missing Phase 15 artifact: {path.relative_to(ROOT)}")

    doc_text = DOC.read_text(encoding="utf-8")
    for phrase in [
        "Autonomous post-v1 industrialization batch",
        "15A",
        "15B",
        "15C",
        "15D",
        "15E",
        "15F",
        "factory must not grant or claim official certification",
    ]:
        require(phrase in doc_text, f"Phase 15 doc missing required phrase: {phrase}")

    policy = load_json(POLICY)
    require(policy.get("phase") == "15A-F", "policy phase mismatch")
    require(policy.get("base_tag_required") == "v0.14.23-operator-autonomy-dashboard-v1-readiness-pack", "base tag requirement mismatch")
    require_bool(policy, "validators_must_be_read_only", True)
    require_bool(policy, "tests_must_use_temporary_audit_outputs", True)
    require_bool(policy, "fresh_clone_replay_required", True)
    require_bool(policy, "factory_must_not_self_certify", True)

    audit = load_json(AUDIT)
    require(audit.get("schema_version") == "autonomous-post-v1-industrialization-batch.v1", "audit schema mismatch")
    require(audit.get("phase") == "15A-F", "audit phase mismatch")
    require(audit.get("status") == "AUTONOMOUS_POST_V1_INDUSTRIALIZATION_READY", "audit status mismatch")
    require_bool(audit, "governed_self_evolution_enabled", True)
    require_bool(audit, "validators_are_read_only", True)
    require_bool(audit, "tests_use_temporary_audit_outputs", True)
    require_bool(audit, "fresh_clone_replay_required", True)
    require_bool(audit, "factory_does_not_self_certify", True)
    require_bool(audit, "official_certification_claimed", False)
    require_bool(audit, "certification_ready_not_certified_boundary_preserved", True)
    require_bool(audit, "read_only_gates_passed", True)
    batch_phases = audit.get("batch_phases")
    require(isinstance(batch_phases, list) and batch_phases == ["15A", "15B", "15C", "15D", "15E", "15F"], "batch phases mismatch")

    replay = load_json(FRESH_REPLAY)
    require(replay.get("schema_version") == "tagged-v1-fresh-clone-replay-result.v1", "fresh replay schema mismatch")
    require(replay.get("status") == "PASS", "fresh replay did not pass")
    require(replay.get("base_tag_replayed") == "v0.14.23-operator-autonomy-dashboard-v1-readiness-pack", "fresh replay base tag mismatch")
    require_bool(replay, "fresh_clone_replay_performed", True)
    require_bool(replay, "phase13g_guardrail_replayed", True)
    require_bool(replay, "phase14yz_readiness_validator_replayed", True)
    require_bool(replay, "phase14yz_targeted_tests_replayed", True)
    require_bool(replay, "official_certification_claimed", False)

    print("Phase 15 autonomous post-v1 industrialization artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
