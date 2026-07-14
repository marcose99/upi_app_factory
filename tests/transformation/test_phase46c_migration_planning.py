from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.transformation_controller import phase46a, phase46c


def finding(
    path: str,
    *,
    category: str = "IDENTITY_FACTORY\x46ROMNOTHING",
    classification: str = "CURRENT_PRODUCT_IDENTITY",
) -> phase46a.Finding:
    return phase46a.Finding(
        finding_id="F-1",
        category=category,
        classification=classification,
        path=path,
        line=1,
        matched_text="legacy",
        context="legacy identity reference",
        rule_id=category,
    )


def policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "phase": "46C",
        "mode": "planning_only",
        "llm": {
            "enabled": False,
            "allowed_calls": 0,
        },
        "generated_application_prefixes": [
            "workspace/factory_generated/",
        ],
        "historical_classifications": [
            "HISTORICAL_EVIDENCE",
        ],
        "technical_identity_categories": [
            "IDENTITY_LEGACY_TECHNICAL",
        ],
        "display_identity_categories": [
            "IDENTITY_FACTORY\x46ROMNOTHING",
            "IDENTITY_LEGACY_DISPLAY",
        ],
        "path_reference_categories": [
            "PATH_ABSOLUTE",
            "PATH_LEGACY_REPOSITORY",
        ],
        "migration_waves": [
            {"wave": "W0", "name": "Controls"},
            {"wave": "W1", "name": "Display contracts"},
            {"wave": "W2", "name": "Path neutrality"},
            {"wave": "W3", "name": "Technical compatibility"},
            {"wave": "W4", "name": "Physical rename"},
            {"wave": "W5", "name": "Compatibility retirement"},
        ],
        "compatibility_aliases": [
            {
                "legacy": "upi_dispute_resolution\x5ffactory",
                "canonical": "upi_app_factory",
            }
        ],
        "human_gates": [
            "local_checkout_rename",
            "remote_repository_rename",
        ],
        "prohibited_actions": [
            "repository_mutation",
            "commit",
            "merge",
            "tag",
            "push",
            "release",
        ],
        "max_findings": 100,
    }


def test_load_policy_rejects_non_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "policies" / "identity_migration_policy.json"
    path.parent.mkdir()
    path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(
        phase46c,
        "DEFAULT_POLICY",
        Path("policies/identity_migration_policy.json"),
    )
    with pytest.raises(phase46c.MigrationPlanningError):
        phase46c.load_policy(tmp_path)


def test_load_policy_rejects_enabled_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "policies" / "identity_migration_policy.json"
    path.parent.mkdir()
    payload = policy()
    payload["llm"] = {"enabled": True, "allowed_calls": 1}
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        phase46c,
        "DEFAULT_POLICY",
        Path("policies/identity_migration_policy.json"),
    )
    with pytest.raises(phase46c.MigrationPlanningError):
        phase46c.load_policy(tmp_path)


def test_generated_application_is_excluded() -> None:
    decision = phase46c.classify_finding(
        finding(
            "workspace/factory_generated/app/README.md",
        ),
        policy(),
    )
    assert decision.decision == "EXCLUDE_GENERATED_APPLICATION"
    assert decision.wave == "W0"
    assert decision.mutation_allowed is False


def test_historical_evidence_is_immutable() -> None:
    decision = phase46c.classify_finding(
        finding(
            "docs/history.md",
            classification="HISTORICAL_EVIDENCE",
        ),
        policy(),
    )
    assert decision.decision == "PRESERVE_HISTORICAL_EVIDENCE"
    assert decision.compatibility_required is False


def test_test_contract_requires_contract_first_migration() -> None:
    decision = phase46c.classify_finding(
        finding("tests/test_identity_contract.py"),
        policy(),
    )
    assert decision.decision == ("PRESERVE_TEST_CONTRACT_AND_PLAN_UPDATE")
    assert decision.compatibility_required is True
    assert decision.wave == "W1"


def test_technical_identity_requires_alias() -> None:
    decision = phase46c.classify_finding(
        finding(
            "src/package.py",
            category="IDENTITY_LEGACY_TECHNICAL",
        ),
        policy(),
    )
    assert decision.decision == ("ADD_COMPATIBILITY_ALIAS_BEFORE_MIGRATION")
    assert decision.wave == "W3"


def test_display_identity_is_contract_first() -> None:
    decision = phase46c.classify_finding(
        finding("README.md"),
        policy(),
    )
    assert decision.decision == ("PLAN_CONTRACT_FIRST_DISPLAY_MIGRATION")
    assert decision.compatibility_required is True


def test_path_reference_uses_path_neutrality_wave() -> None:
    decision = phase46c.classify_finding(
        finding(
            "config/runtime.yaml",
            category="PATH_ABSOLUTE",
        ),
        policy(),
    )
    assert decision.decision == "PLAN_PATH_NEUTRALITY_MIGRATION"
    assert decision.wave == "W2"


def test_unknown_finding_is_deterministic_review() -> None:
    decision = phase46c.classify_finding(
        finding(
            "misc.txt",
            category="UNCLASSIFIED_REFERENCE",
        ),
        policy(),
    )
    assert decision.decision == "DETERMINISTIC_REVIEW_REQUIRED"
    assert decision.mutation_allowed is False


def test_build_plan_contains_all_waves_and_aliases() -> None:
    findings = [
        finding("README.md"),
        finding(
            "src/package.py",
            category="IDENTITY_LEGACY_TECHNICAL",
        ),
    ]
    graph = phase46a.create_task_graph(findings)
    plan = phase46c.build_migration_plan(
        findings,
        graph,
        policy(),
    )
    assert plan["decision_count"] == 2
    assert len(plan["migration_waves"]) == 6
    assert len(plan["compatibility_aliases"]) == 1
    assert plan["mutation_allowed"] is False
    assert plan["llm_calls"] == 0


def test_task_gate_keeps_repo_rename_human_only() -> None:
    graph = phase46a.create_task_graph([])
    decisions = phase46c.task_gate_decisions(graph)
    rename = next(item for item in decisions if item["task_id"] == "T-007")
    assert rename["decision"] == "HUMAN_GATE"
    assert rename["protected_action"] is True
    assert rename["mutation_allowed"] is False
    assert rename["llm_eligible"] is False


def test_evidence_manifest_excludes_itself(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "phase46c_evidence_manifest.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    manifest = phase46c.evidence_manifest(tmp_path)
    paths = {item["path"] for item in manifest["files"]}
    assert paths == {"run.json"}
