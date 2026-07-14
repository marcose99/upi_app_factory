from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.transformation_controller import phase46a, phase46b


def finding(
    path: str,
    category: str = "IDENTITY_FACTORY\x46ROMNOTHING",
    classification: str = "CURRENT_PRODUCT_IDENTITY",
) -> phase46a.Finding:
    return phase46a.Finding(
        finding_id="F-1",
        category=category,
        classification=classification,
        path=path,
        line=1,
        matched_text="Factory\x46romNothing",
        context="Factory\x46romNothing",
        rule_id=category,
    )


def policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "llm": {"enabled": False},
        "protected_actions": {"allow": []},
        "safe_branding_batch": {
            "allowed_categories": [
                "IDENTITY_FACTORY\x46ROMNOTHING",
                "IDENTITY_LEGACY_DISPLAY",
            ],
            "allowed_classifications": ["CURRENT_PRODUCT_IDENTITY"],
            "allowed_suffixes": [".md", ".yaml"],
            "excluded_prefixes": [
                "tests/",
                "workspace/factory_generated/",
                "docs/phase46a/",
                "docs/phase46b/",
                "tools/transformation_controller/",
            ],
            "replacements": {
                "UPI Dispute Resolution\x20Factory": "UPI App Factory",
                "Factory\x46romNothing": "UPI App Factory",
            },
            "max_files": 10,
            "max_file_bytes": 10000,
            "max_total_bytes": 10000,
        },
        "repair": {"max_attempts": 1},
    }


def test_discover_branding_candidates_selects_current_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    path.write_text("Factory\x46romNothing\n", encoding="utf-8")
    candidates = phase46b.discover_branding_candidates(
        tmp_path,
        [finding("README.md")],
        policy(),
    )
    assert [item.path for item in candidates] == ["README.md"]
    assert candidates[0].replacement_counts == {"Factory\x46romNothing": 1}


def test_discover_branding_candidates_excludes_tests(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tests" / "test_brand.py"
    path.parent.mkdir()
    path.write_text("Factory\x46romNothing\n", encoding="utf-8")
    candidates = phase46b.discover_branding_candidates(
        tmp_path,
        [finding("tests/test_brand.py")],
        policy(),
    )
    assert candidates == []


def test_discover_branding_candidates_excludes_historical_classification(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.md"
    path.write_text("Factory\x46romNothing\n", encoding="utf-8")
    candidates = phase46b.discover_branding_candidates(
        tmp_path,
        [finding("history.md", classification="HISTORICAL_EVIDENCE")],
        policy(),
    )
    assert candidates == []


def test_discover_branding_candidates_does_not_migrate_technical_identifier(
    tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    path.write_text("upi_dispute_resolution\x5ffactory\n", encoding="utf-8")
    candidates = phase46b.discover_branding_candidates(
        tmp_path,
        [
            finding(
                "README.md",
                category="IDENTITY_LEGACY_TECHNICAL",
            )
        ],
        policy(),
    )
    assert candidates == []


def test_apply_and_verify_candidates_preserve_file_mode(
    tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    path.write_text("Factory\x46romNothing\n", encoding="utf-8")
    os.chmod(path, 0o640)
    candidates = phase46b.discover_branding_candidates(
        tmp_path,
        [finding("README.md")],
        policy(),
    )
    phase46b.apply_candidates(tmp_path, candidates, policy())
    report = phase46b.verify_applied_candidates(
        tmp_path,
        candidates,
        policy(),
    )
    assert path.read_text(encoding="utf-8") == "UPI App Factory\n"
    assert oct(path.stat().st_mode & 0o777) == "0o640"
    assert report["status"] == "PASSED"


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    root.mkdir()
    run_dir.mkdir()
    path = root / "README.md"
    path.write_text("Factory\x46romNothing\n", encoding="utf-8")
    candidates = phase46b.discover_branding_candidates(
        root,
        [finding("README.md")],
        policy(),
    )
    phase46b.create_backup(root, candidates, run_dir)
    phase46b.apply_candidates(root, candidates, policy())
    restored = phase46b.restore_backup(root, run_dir)
    assert restored == ["README.md"]
    assert path.read_text(encoding="utf-8") == "Factory\x46romNothing\n"


def test_checkpoint_chain_verifies_and_detects_tamper(
    tmp_path: Path,
) -> None:
    ledger = phase46b.CheckpointLedger(tmp_path)
    ledger.append("PREFLIGHT", "PASSED", {"llm_calls": 0})
    ledger.append("PLAN", "PASSED", {"candidate_count": 1})
    assert phase46b.verify_checkpoint_chain(tmp_path)["checkpoints_verified"] == 2

    checkpoint = next((tmp_path / "checkpoints").glob("002_*.json"))
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["details"]["candidate_count"] = 2
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(phase46b.ExecutionPolicyError):
        phase46b.verify_checkpoint_chain(tmp_path)


def test_task_decisions_keep_protected_rename_as_human_gate() -> None:
    graph = phase46a.create_task_graph([])
    decisions = phase46b.task_execution_decisions(
        graph,
        candidate_count=1,
    )
    rename = next(item for item in decisions if item["task_id"] == "T-007")
    technical = next(item for item in decisions if item["task_id"] == "T-003")
    branding = next(item for item in decisions if item["task_id"] == "T-004")
    assert rename["decision"] == "HUMAN_GATE"
    assert rename["protected_action"] is True
    assert technical["decision"] == "DEFERRED"
    assert branding["decision"] == "AUTO_EXECUTABLE"
    assert all(item["llm_eligible"] is False for item in decisions)


def test_policy_rejects_llm_enablement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "policies" / "autonomous_execution_policy.json"
    policy_path.parent.mkdir()
    payload = policy()
    payload["llm"] = {"enabled": True}
    policy_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        phase46b,
        "DEFAULT_POLICY",
        Path("policies/autonomous_execution_policy.json"),
    )
    with pytest.raises(phase46b.ExecutionPolicyError):
        phase46b.load_policy(tmp_path)


def test_evidence_manifest_excludes_itself(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "phase46b_evidence_manifest.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    manifest = phase46b.evidence_manifest(tmp_path)
    paths = {item["path"] for item in manifest["files"]}
    assert paths == {"run.json"}
    expected = hashlib.sha256(b"{}\n").hexdigest()
    assert manifest["files"][0]["sha256"] == expected


def test_validation_runtime_noise_paths_are_normalized() -> None:
    payload = policy()
    payload["validation_runtime_noise_paths"] = ["workspace/runtime/report.json"]
    assert phase46b.validation_runtime_noise_paths(payload) == ["workspace/runtime/report.json"]


def test_validation_runtime_noise_paths_reject_non_list() -> None:
    payload = policy()
    payload["validation_runtime_noise_paths"] = "runtime.json"
    with pytest.raises(phase46b.ExecutionPolicyError):
        phase46b.validation_runtime_noise_paths(payload)
