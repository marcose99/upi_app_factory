from __future__ import annotations

import subprocess
import sys
from typing import Any, cast

from scripts.run_autonomous_safe_repair_catalog_operator_loop import (
    BLOCKED_AUTONOMOUS_ACTIONS,
    HUMAN_GATED_ACTIONS,
    SAFE_REPAIR_CATALOG,
    STATUS,
    build_autonomous_safe_repair_catalog_operator_loop,
    validate_autonomous_safe_repair_catalog_operator_loop,
)

JsonDict = dict[str, Any]


def test_phase14t_plan_is_ready() -> None:
    audit = build_autonomous_safe_repair_catalog_operator_loop(execute_readonly_gates=False)
    assert audit["status"] == STATUS
    assert audit["safe_repair_catalog_operator_loop_enabled"] is True
    assert audit["safe_repair_auto_apply_allowed_only_when_policy_cataloged"] is True
    assert audit["unknown_failure_class_behavior"] == "stop_and_require_human_review_or_new_policy"
    assert validate_autonomous_safe_repair_catalog_operator_loop(audit) == []


def test_safe_repair_catalog_contains_known_low_risk_repairs() -> None:
    repair_ids = {str(item["repair_id"]) for item in SAFE_REPAIR_CATALOG}
    assert "ruff_unused_variable_cleanup" in repair_ids
    assert "ruff_unused_import_cleanup" in repair_ids
    assert "mypy_validator_json_object_cast" in repair_ids
    assert "generated_app_runtime_cache_cleanup" in repair_ids
    assert "ignored_workspace_audit_artifact_forced_staging" in repair_ids


def test_catalog_entries_are_policy_bounded() -> None:
    for entry in SAFE_REPAIR_CATALOG:
        assert entry["allowed_auto_apply_when_policy_cataloged"] is True
        assert isinstance(entry["scope_limit"], str)
        assert entry["scope_limit"]
        assert isinstance(entry["failure_signatures"], list)


def test_human_gated_boundaries_are_preserved() -> None:
    audit = build_autonomous_safe_repair_catalog_operator_loop()
    for action in ("merge", "tag", "push", "release", "official_certification_claims"):
        assert action in HUMAN_GATED_ACTIONS
    for action in ("auto_merge", "auto_tag", "auto_push", "auto_release", "auto_certify"):
        assert action in BLOCKED_AUTONOMOUS_ACTIONS
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_push_performed"] is False
    assert audit["official_certification_claimed"] is False


def test_readonly_gate_specs_are_parallel_safe_and_readonly() -> None:
    audit = build_autonomous_safe_repair_catalog_operator_loop()
    specs = cast(list[JsonDict], audit["read_only_gate_specs"])
    assert len(specs) >= 5
    assert all(spec["read_only"] is True for spec in specs)
    assert all(spec["parallel_safe"] is True for spec in specs)


def test_phase14t_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14t_autonomous_safe_repair_catalog_operator_loop.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
