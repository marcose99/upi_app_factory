from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.lifecycle_orchestrator import campaign
from tools.lifecycle_orchestrator.campaign_payloads import install_phase
from tools.lifecycle_orchestrator.repairs import (
    classify_failure_gate,
    latest_phase_run,
    rollback_to_implemented,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def active_manifest(phase: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": phase,
        "name": f"Phase {phase}",
        "status": "ACTIVE",
        "base_branch": "main",
        "feature_branch": f"phase{phase.lower()}/test",
        "commit_message": "test: campaign",
        "candidate_paths": ["test.txt"],
        "implementation_commands": [],
        "targeted_validation_commands": [],
        "full_validation_commands": [],
        "post_restore_validation_commands": [],
        "runtime_noise_paths": [],
        "protected_actions": ["commit", "merge", "push"],
        "llm": {"enabled": False, "allowed_calls": 0},
    }


def test_parse_approvals_accepts_exact_protected_set() -> None:
    assert campaign.parse_approvals("commit,merge,push") == {
        "commit",
        "merge",
        "push",
    }


@pytest.mark.parametrize(
    "value",
    [
        "",
        "commit",
        "commit,merge",
        "commit,merge,push,tag",
        "release,commit,merge,push",
    ],
)
def test_parse_approvals_rejects_incomplete_or_excessive_set(
    value: str,
) -> None:
    with pytest.raises(campaign.CampaignError):
        campaign.parse_approvals(value)


def test_validate_campaign_resolves_relative_manifests(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    manifest_path = root / "config/lifecycle/phases/phase99a.json"
    write_json(manifest_path, active_manifest("99A"))
    campaign_path = root / "campaign.json"
    write_json(
        campaign_path,
        {
            "schema_version": 1,
            "campaign": "test-campaign",
            "phases": [
                {
                    "phase": "99A",
                    "manifest": (
                        "config/lifecycle/phases/phase99a.json"
                    ),
                }
            ],
            "max_repair_attempts": 2,
        },
    )
    result = campaign.validate_campaign(campaign_path, root)
    assert result["campaign_id"] == "test-campaign"
    assert result["phases"][0]["phase"] == "99A"


def test_validate_campaign_rejects_llm_enabled_phase(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    manifest = active_manifest("99A")
    manifest["llm"] = {"enabled": True, "allowed_calls": 1}
    manifest_path = root / "phase99a.json"
    write_json(manifest_path, manifest)
    campaign_path = root / "campaign.json"
    write_json(
        campaign_path,
        {
            "schema_version": 1,
            "campaign": "test-campaign",
            "phases": [
                {"phase": "99A", "manifest": "phase99a.json"}
            ],
        },
    )
    with pytest.raises(campaign.CampaignError, match="prohibit LLM"):
        campaign.validate_campaign(campaign_path, root)


def test_latest_phase_run_returns_latest_directory(
    tmp_path: Path,
) -> None:
    for run_id in ("46h-001", "46h-002"):
        write_json(
            tmp_path / "lifecycle_runs" / run_id / "run.json",
            {"run_id": run_id},
        )
    latest = latest_phase_run(tmp_path, "46H")
    assert latest is not None
    assert latest.name == "46h-002"


def test_rollback_to_implemented_invalidates_stale_evidence(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "run.json",
        {
            "completed_states": [
                "PREFLIGHT_PASSED",
                "WORKTREE_READY",
                "IMPLEMENTED",
                "TARGETED_VALIDATED",
                "CANDIDATE_VERIFIED",
            ],
            "step_evidence": {
                "PREFLIGHT_PASSED": {},
                "WORKTREE_READY": {},
                "IMPLEMENTED": {},
                "TARGETED_VALIDATED": {},
                "CANDIDATE_VERIFIED": {},
            },
            "status": "FAILED",
            "current_state": "CANDIDATE_VERIFIED",
            "failure": {"message": "Ruff"},
        },
    )
    write_json(run_dir / "steps/04_targeted.json", {})
    write_json(run_dir / "steps/05_candidate.json", {})
    write_json(run_dir / "candidate_manifest.json", {})
    report = rollback_to_implemented(run_dir)
    assert report["new_state"] == "IMPLEMENTED"
    state = json.loads(
        (run_dir / "run.json").read_text(encoding="utf-8")
    )
    assert state["completed_states"] == [
        "PREFLIGHT_PASSED",
        "WORKTREE_READY",
        "IMPLEMENTED",
    ]
    assert not (run_dir / "candidate_manifest.json").exists()


def test_phase46h_payload_install_is_atomic_and_complete(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "config/identity_compatibility_runtime.json",
        {"schema_version": 1},
    )
    report = install_phase("46H", tmp_path)
    assert report["status"] == "PASSED"
    assert report["written_file_count"] == 7
    runtime = json.loads(
        (
            tmp_path / "config/identity_compatibility_runtime.json"
        ).read_text(encoding="utf-8")
    )
    assert runtime["runtime_root_posture"] == "PATH_NEUTRAL"


def test_phase46i_payload_install_preserves_compatibility(
    tmp_path: Path,
) -> None:
    write_json(
        tmp_path / "config/identity_compatibility_runtime.json",
        {"schema_version": 1},
    )
    report = install_phase("46I", tmp_path)
    assert report["status"] == "PASSED"
    runtime = json.loads(
        (
            tmp_path / "config/identity_compatibility_runtime.json"
        ).read_text(encoding="utf-8")
    )
    assert runtime["canonical_technical_identifier"] == "upi_app_factory"
    assert runtime["legacy_technical_identifier"] == (
        "upi_dispute_resolution_factory"
    )

def test_draft_manifest_is_activated_in_campaign_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "config/lifecycle/phases/phase99a.json"
    manifest = active_manifest("99A")
    manifest["status"] = "DRAFT"
    write_json(source, manifest)
    item = {
        "phase": "99A",
        "manifest": str(source),
        "manifest_status": "DRAFT",
    }
    active = campaign.materialize_active_manifest(
        item,
        tmp_path / "campaign-run",
    )
    source_value = json.loads(source.read_text(encoding="utf-8"))
    active_value = json.loads(active.read_text(encoding="utf-8"))
    assert source_value["status"] == "DRAFT"
    assert active_value["status"] == "ACTIVE"


def test_pytest_failure_is_classified_and_not_misrouted() -> None:
    run = {
        "failure": {
            "message": "Command failed (Pytest): python -m pytest -q"
        }
    }
    assert classify_failure_gate(run) == "Pytest"


def test_phase46h_payload_contains_no_machine_checkout_literal() -> None:
    from tools.lifecycle_orchestrator.campaign_payloads import (
        PHASE_PAYLOADS,
    )

    module = PHASE_PAYLOADS["46H"][
        "tools/transformation_controller/phase46h.py"
    ]
    assert "/home/marcose/" not in module
    assert "contains_unapproved_absolute_path" in module



def test_future_manifests_provision_prerequisites_first() -> None:
    for relative in (
        "config/lifecycle/phases/phase46h.json",
        "config/lifecycle/phases/phase46i.json",
        "config/lifecycle/phases/phase46j.json",
    ):
        manifest = json.loads(
            (Path(__file__).resolve().parents[2] / relative).read_text(encoding="utf-8")
        )
        first = manifest["implementation_commands"][0]
        assert first["name"] == (
            "Provision ignored lifecycle prerequisites"
        )
        assert "provision-prerequisites" in first["argv"]

