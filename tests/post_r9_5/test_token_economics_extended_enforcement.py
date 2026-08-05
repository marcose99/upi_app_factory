from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from factory.prerequisite_artifacts import restore_mutable_test_roots, snapshot_mutable_test_roots
from factory.token_economics import (
    ArtifactOwnershipError,
    LedgerStore,
    TokenEconomicsError,
    build_token_economics_operator_surface,
    build_token_economics_summary,
    classify_generated_application_token_economics,
    load_artifact_ownership_registry,
    load_governance_policy,
    resolve_artifact_owner,
    resolve_rate_card,
    redacted_evidence_report,
    validate_artifact_path,
)


ROOT = Path(__file__).resolve().parents[2]
TOKEN_CONFIG_ROOT = ROOT / "config" / "token_economics"


def _copy_config_root(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return tmp_path / "config" / "token_economics"


def test_te_031_te_035_te_048_owner_resolution_and_runtime_commit_rules_are_fail_closed(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_root(tmp_path)
    registry = load_artifact_ownership_registry(config_root)
    assert len(registry["families"]) >= 4

    config_owner = resolve_artifact_owner(
        "config/token_economics/governance_policy.json",
        config_root=config_root,
    )
    runtime_owner = resolve_artifact_owner(
        "workspace/token_economics_runtime/ledger.jsonl",
        config_root=config_root,
    )
    assert config_owner["candidate_commit_allowed"] is True
    assert runtime_owner["candidate_commit_allowed"] is False
    assert runtime_owner["runtime_root"] == "workspace/token_economics_runtime"

    registry_path = config_root / "artifact_ownership_registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["families"][1]["candidate_commit_allowed"] = True
    registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ArtifactOwnershipError, match="must not allow candidate commits"):
        load_artifact_ownership_registry(config_root)


def test_te_032_te_033_path_collisions_and_symlinks_are_rejected(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_root(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    governed = project_root / "config" / "token_economics" / "governance_policy.json"
    governed.parent.mkdir(parents=True, exist_ok=True)
    governed.write_text("{}", encoding="utf-8")

    resolved = validate_artifact_path(
        governed,
        project_root=project_root,
        config_root=config_root,
    )
    assert resolved["family_id"] == "token_economics_configuration"

    registry_path = config_root / "artifact_ownership_registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["families"].append(
        {
            "family_id": "overlap",
            "logical_owner": "factory_platform_owner",
            "producer": "test",
            "artifact_kind": "configuration",
            "candidate_commit_allowed": True,
            "persistence_policy": "durable_repository_owned",
            "stable_fields": ["schema_version"],
            "volatile_fields": [],
            "runtime_root": None,
            "deterministic_contract": "exact_bytes",
            "path_patterns": ["config/token_economics/governance_policy.json"],
        }
    )
    registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ArtifactOwnershipError, match="multiple families"):
        resolve_artifact_owner(
            "config/token_economics/governance_policy.json",
            config_root=config_root,
        )

    symlink_path = project_root / "config" / "token_economics" / "governance_policy_link.json"
    symlink_path.symlink_to(governed)
    with pytest.raises(ArtifactOwnershipError, match="symlinked artifacts are rejected"):
        validate_artifact_path(
            symlink_path,
            project_root=project_root,
            config_root=config_root,
        )


def test_te_034_te_036_snapshot_restore_and_ledger_accounting_remain_deterministic(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    runtime_root = project_root / "workspace" / "deep_engineering_campaign"
    recipient_root = project_root / "factory_governance" / "phase68_70" / "recipient_replay_output"
    original_runtime = runtime_root / "generated_app" / "fixture.txt"
    original_recipient = recipient_root / "recipient_replay_result.json"
    original_runtime.parent.mkdir(parents=True, exist_ok=True)
    recipient_root.mkdir(parents=True, exist_ok=True)
    original_runtime.write_text("original-runtime\n", encoding="utf-8")
    original_recipient.write_text('{"status": "PASS"}\n', encoding="utf-8")

    snapshot = snapshot_mutable_test_roots(project_root)
    original_runtime.write_text("mutated-runtime\n", encoding="utf-8")
    (runtime_root / "new.json").write_text('{"drift": true}\n', encoding="utf-8")
    restored = restore_mutable_test_roots(snapshot)
    assert restored["status"] == "RESTORED"
    assert original_runtime.read_text(encoding="utf-8") == "original-runtime\n"
    assert original_recipient.read_text(encoding="utf-8") == '{"status": "PASS"}\n'
    assert not (runtime_root / "new.json").exists()

    ledger = LedgerStore(tmp_path / "ledger.jsonl")
    first = ledger.append(
        {"provider_turn_id": "turn-001", "settlement": {"rounded_amount": "1.0000000"}}
    )
    second = ledger.append(
        {"provider_turn_id": "turn-002", "settlement": {"rounded_amount": "2.0000000"}}
    )
    assert ledger.read_all() == [first, second]
    with pytest.raises(TokenEconomicsError, match="duplicate ledger identity rejected"):
        ledger.append({"provider_turn_id": "turn-002"})


def test_te_037_te_038_te_039_te_040_te_041_policy_contracts_require_human_rights_and_legal_hold(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_root(tmp_path)
    policy = load_governance_policy(config_root)
    rights = set(policy["decision_rights"]["human_authority"])
    assert {"budget_exception", "rate_card_publication", "certification_claim"} <= rights
    assert policy["retention_policy"]["legal_hold_machine_readable"] is True
    assert policy["compatibility_mappings"]["focus"] == "compatibility_mapping_only"
    assert (
        policy["compatibility_mappings"]["opentelemetry_genai"]
        == "versioned_compatibility_adapter"
    )

    policy_path = config_root / "governance_policy.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["decision_rights"]["human_authority"].remove("budget_exception")
    policy_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(TokenEconomicsError, match="budget_exception"):
        load_governance_policy(config_root)

    payload["decision_rights"]["human_authority"].append("budget_exception")
    payload["retention_policy"]["legal_hold_machine_readable"] = False
    policy_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(TokenEconomicsError, match="legal hold"):
        load_governance_policy(config_root)

    payload["retention_policy"]["legal_hold_machine_readable"] = True
    payload["compatibility_mappings"]["focus"] = "rewritable"
    policy_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(TokenEconomicsError, match="mapping-only"):
        load_governance_policy(config_root)


def test_te_042_te_043_compact_redaction_and_generated_application_applicability_are_truthful(
) -> None:
    report = redacted_evidence_report(
        [
            {
                "prompt": "restricted prompt",
                "response": "restricted response",
                "reasoning": "restricted reasoning",
                "settlement": {"rounded_amount": "1.2500000"},
            }
        ]
    )
    compact = report["records"][0]
    assert "prompt" not in compact
    assert compact["prompt_size_bytes"] > 0
    assert compact["response_sha256"]

    not_applicable = classify_generated_application_token_economics(
        requirements_text="Deterministic local mocked dispute workflow only.",
        runtime_llm_calls_default=0,
    )
    applicable = classify_generated_application_token_economics(
        requirements_text="This generated workflow routes to a model for summarization.",
        runtime_llm_calls_default=1,
    )
    assert not_applicable["status"] == "NOT_APPLICABLE"
    assert applicable["status"] == "APPLICABLE"


def test_te_044_te_045_operator_surface_separates_budget_from_runtime_views(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    generated_root = (
        tmp_path
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "generated_application"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "generation_metadata.json").write_text(
        json.dumps(
            {
                "llm_calls": 0,
                "schema_version": "upi-failed-debit-generated-application-evidence.v3",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger = LedgerStore(tmp_path / "workspace" / "token_economics_runtime" / "ledger.jsonl")
    ledger.append(
        {
            "stage_id": "review",
            "run_id": "run-001",
            "application_id": "upi_dispute_resolution",
            "accepted_outcome": True,
            "normalized_usage": {
                "status": "OBSERVED",
                "total_input_tokens": 100,
                "cache_read_input_tokens": 20,
                "cache_write_input_tokens": 10,
                "uncached_input_tokens": 70,
                "total_output_tokens": 30,
                "reasoning_output_tokens": 10,
            },
            "settlement": {"rounded_amount": "0.7500000"},
            "reconciliation": {"status": "RECONCILED"},
        }
    )

    summary = build_token_economics_summary(tmp_path)
    surface = build_token_economics_operator_surface(tmp_path)
    assert summary["mock_boundaries"]["live_provider_calls_allowed"] is False
    assert summary["mock_boundaries"]["real_payment_calls"] == "disabled"
    assert surface["budget_controls"]["status"] == "available"
    assert surface["usage_views"]["observed"]["status"] == "RECORDED"
    assert surface["default_stage_budget"]["budget_id"] != ""
    assert surface["usage_views"]["observed"]["payload"] != surface["default_stage_budget"]


def test_te_046_te_047_te_049_rate_card_migrations_and_matrix_inventory_stay_explicit(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_root(tmp_path)
    lookup = {
        "provider": "openai",
        "billing_surface": "chatgpt_credit",
        "model_resolved": "gpt-5.4",
        "model_version": "2026-07-28",
        "service_tier": "standard",
        "context_band": "default",
        "modality": "text",
        "region_or_residency": "global",
        "currency_or_credit_unit": "chatgpt_credit",
        "contract_id": "local-governed-reference-chatgpt-credit",
    }
    resolved = resolve_rate_card(lookup, config_root=config_root)
    assert resolved["rate_card_id"] == "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4"

    failed_lookup = dict(lookup)
    failed_lookup["model_version"] = "2026-08-01"
    with pytest.raises(TokenEconomicsError, match="unknown or out-of-interval rate-card key"):
        resolve_rate_card(failed_lookup, config_root=config_root)

    registry = load_artifact_ownership_registry(config_root)
    assert registry["families"]
    matrix = json.loads(
        (TOKEN_CONFIG_ROOT / "mandatory_test_matrix.json").read_text(encoding="utf-8")
    )
    assert [item["case_id"] for item in matrix["cases"]] == [
        f"TE-{index:03d}" for index in range(1, 31)
    ]
    assert [item["case_id"] for item in matrix["extended_cases"]] == [
        f"TE-{index:03d}" for index in range(31, 50)
    ]
