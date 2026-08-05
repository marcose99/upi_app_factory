from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from factory.token_economics import (
    LedgerStore,
    RateCardError,
    UsageNormalizationError,
    authorize_budget,
    estimate_usage_cost,
    load_budget_envelope,
    load_rate_cards,
    normalize_usage,
    reconcile_records,
    resolve_rate_card,
    state_transition_path,
    summarize_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
TOKEN_CONFIG_ROOT = ROOT / "config" / "token_economics"


def _copy_token_config(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return tmp_path / "config" / "token_economics"


def _write_rate_card(path: Path, payload: dict[str, object]) -> None:
    material = {key: value for key, value in payload.items() if key != "integrity"}
    payload["integrity"] = {
        "sha256": hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_lookup(**overrides: str) -> dict[str, str]:
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
    lookup.update(overrides)
    return lookup


def test_mandatory_matrix_lists_all_30_cases() -> None:
    matrix = json.loads((TOKEN_CONFIG_ROOT / "mandatory_test_matrix.json").read_text(encoding="utf-8"))

    assert matrix["schema_version"] == "token-economics-mandatory-test-matrix.v1"
    assert len(matrix["cases"]) == 30
    assert [item["case_id"] for item in matrix["cases"]] == [f"TE-{index:03d}" for index in range(1, 31)]
    assert sum(1 for item in matrix["cases"] if item["coverage_kind"] == "automated_test") == 28
    assert sum(1 for item in matrix["cases"] if item["coverage_kind"] == "operational_gate") == 2
    for item in matrix["cases"]:
        assert item["references"]
        if item["coverage_kind"] == "automated_test":
            for reference in item["references"]:
                path_text = str(reference).split("::", 1)[0]
                assert (ROOT / path_text).is_file(), reference


def test_cached_heavy_turn_above_raw_anomaly_below_economic_limit(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    budget = load_budget_envelope(config_root / "budgets" / "default_stage_budget.json")
    usage = {
        "input_tokens": budget["raw_input_anomaly_limit"] + 10,
        "cached_input_tokens": budget["raw_input_anomaly_limit"],
        "cache_write_input_tokens": 5,
        "output_tokens": 10,
        "reasoning_output_tokens": 4,
    }
    settlement = estimate_usage_cost(
        usage,
        rate_card_id="openai-codex-chatgpt-credit-2026-07-28-gpt-5.4",
        config_root=config_root,
    )

    decision = authorize_budget(
        budget,
        reserved_amount=settlement["rounded_amount"],
        observed_raw_input_tokens=usage["input_tokens"],
        observed_output_tokens=usage["output_tokens"],
    )

    assert "raw_input_anomaly_limit" in decision["blocks"]
    assert "economic_budget" not in decision["blocks"]


def test_expensive_uncached_turn_below_raw_threshold_above_economic_limit(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    budget = load_budget_envelope(config_root / "budgets" / "default_stage_budget.json")
    usage = {
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 16000000,
        "reasoning_output_tokens": 8000000,
    }
    settlement = estimate_usage_cost(
        usage,
        rate_card_id="openai-codex-chatgpt-credit-2026-07-28-gpt-5.4",
        config_root=config_root,
    )

    decision = authorize_budget(
        budget,
        reserved_amount=settlement["rounded_amount"],
        observed_raw_input_tokens=usage["input_tokens"],
        observed_output_tokens=usage["output_tokens"],
    )

    assert "economic_budget" in decision["blocks"]
    assert "raw_input_anomaly_limit" not in decision["blocks"]


def test_cache_write_pricing_and_rate_card_selection_are_distinct(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    settlement = estimate_usage_cost(
        {
            "input_tokens": 600,
            "cached_input_tokens": 100,
            "cache_write_input_tokens": 100,
            "output_tokens": 50,
            "reasoning_output_tokens": 10,
        },
        rate_card_id="openai-codex-chatgpt-credit-2026-07-28-gpt-5.4",
        config_root=config_root,
    )

    assert settlement["exact_cost_components"]["cache_write_cost"] != settlement["exact_cost_components"]["cache_read_cost"]
    assert settlement["exact_cost_components"]["cache_write_cost"] == "0.0002000"


def test_unknown_rate_card_key_fails_closed(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    with pytest.raises(RateCardError, match="unknown or out-of-interval rate-card key"):
        resolve_rate_card(
            _base_lookup(model_version="2026-08-01"),
            config_root=config_root,
            now=datetime(2026, 7, 29, tzinfo=timezone.utc),
        )


def test_long_context_rate_card_selection_changes_price_band(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    default_card_path = (
        config_root / "rate_cards" / "chatgpt_credit" / "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4.json"
    )
    payload = json.loads(default_card_path.read_text(encoding="utf-8"))
    payload["rate_card_id"] = "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4-long-context"
    payload["context_band"] = "long_context"
    payload["categories"]["output"]["rate"] = "0.0000200"
    _write_rate_card(config_root / "rate_cards" / "chatgpt_credit" / "long_context.json", payload)

    resolved = resolve_rate_card(
        _base_lookup(context_band="long_context"),
        config_root=config_root,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )

    assert resolved["rate_card_id"] == "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4-long-context"


def test_credit_and_usd_rate_cards_do_not_share_units(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    cards = {card.rate_card_id: card for card in load_rate_cards(config_root)}

    assert cards["openai-codex-chatgpt-credit-2026-07-28-gpt-5.4"].currency_or_credit_unit == "chatgpt_credit"
    assert cards["openai-api-usd-2026-07-28-gpt-5.4"].currency_or_credit_unit == "usd"


def test_priority_service_tier_rate_card_changes_price(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    base_path = (
        config_root / "rate_cards" / "chatgpt_credit" / "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4.json"
    )
    payload = json.loads(base_path.read_text(encoding="utf-8"))
    payload["rate_card_id"] = "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4-priority"
    payload["service_tier"] = "priority"
    payload["categories"]["output"]["rate"] = "0.0000180"
    _write_rate_card(config_root / "rate_cards" / "chatgpt_credit" / "priority.json", payload)

    resolved = resolve_rate_card(
        _base_lookup(service_tier="priority"),
        config_root=config_root,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )

    assert resolved["rate_card_id"] == "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4-priority"


def test_completed_over_budget_turn_is_sealed_then_blocked() -> None:
    path = state_transition_path(
        turn_state="TURN_COMPLETED",
        completed_within_budget=False,
        validation_passed=True,
        accepted=True,
    )

    assert path == [
        "AUTHORIZED",
        "PRE_INVOKE_SEALED",
        "IN_PROGRESS",
        "TURN_COMPLETED",
        "COMPLETION_SEALED",
        "MUTATIONS_RECONCILED",
        "OBSERVED_COST_SETTLED",
        "BLOCKED_FURTHER_MODEL_CALLS",
        "DETERMINISTIC_VALIDATION",
        "ACCEPTED",
    ]


def test_completed_turn_can_transition_to_ready_for_governed_review() -> None:
    path = state_transition_path(
        turn_state="TURN_COMPLETED",
        completed_within_budget=True,
        validation_passed=True,
        accepted=None,
        ready_for_governed_review=True,
    )

    assert path[-1] == "READY_FOR_GOVERNED_REVIEW"


def test_incomplete_turn_and_partial_usage_fail_closed() -> None:
    with pytest.raises(UsageNormalizationError, match="partially missing"):
        normalize_usage(
            {
                "input_tokens": 100,
                "cached_input_tokens": 10,
                "output_tokens": 5,
                "reasoning_output_tokens": 1,
            }
        )

    assert state_transition_path(turn_state="TURN_INCOMPLETE")[-1] == "FAILED_CLOSED"


def test_provider_success_after_client_timeout_requires_explicit_recovery() -> None:
    reconciliation = reconcile_records(
        {
            "estimate": {"rounded_amount": "1.0000000"},
            "observed": None,
            "settled": None,
            "provider_ids": {"provider_turn_id": "turn-timeout-001"},
            "completion_status": "PROVIDER_COMPLETED_CLIENT_TIMEOUT",
        }
    )

    assert reconciliation["status"] == "RECONCILIATION_PENDING"
    assert reconciliation["explicit_recovery_required"] is True
    assert reconciliation["retry_permitted"] is False
    assert "ambiguous_provider_completed_client_timeout" in reconciliation["unresolved"]


def test_duplicate_provider_response_and_idempotency_identities_are_rejected(tmp_path: Path) -> None:
    ledger = LedgerStore(tmp_path / "ledger.jsonl")
    ledger.append({"provider_response_id": "resp-001"})
    with pytest.raises(RuntimeError, match="provider_response_id:resp-001"):
        ledger.append({"provider_response_id": "resp-001"})

    ledger.append({"idempotency_key": "idem-001"})
    with pytest.raises(RuntimeError, match="idempotency_key:idem-001"):
        ledger.append({"idempotency_key": "idem-001"})


def test_one_byte_rate_card_evidence_drift_fails_integrity_validation(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    target = (
        config_root / "rate_cards" / "chatgpt_credit" / "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4.json"
    )
    content = target.read_text(encoding="utf-8")
    target.write_text(content.replace("0.0000040", "0.0000041", 1), encoding="utf-8")

    with pytest.raises(RateCardError, match="integrity mismatch"):
        load_rate_cards(config_root)


def test_restart_after_completion_reuses_sealed_identity_without_replay(tmp_path: Path) -> None:
    ledger = LedgerStore(tmp_path / "ledger.jsonl")
    record = ledger.append(
        {
            "turn_state": "TURN_COMPLETED",
            "provider_turn_id": "turn-complete-001",
            "idempotency_key": "idem-complete-001",
            "settlement": {"rounded_amount": "1.2500000"},
        }
    )

    assert record["turn_state"] == "TURN_COMPLETED"
    with pytest.raises(RuntimeError, match="provider_turn_id:turn-complete-001"):
        ledger.append(
            {
                "turn_state": "TURN_COMPLETED",
                "provider_turn_id": "turn-complete-001",
                "idempotency_key": "idem-complete-001",
            }
        )


def test_model_version_migration_requires_explicit_rate_card_match(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    resolved = resolve_rate_card(
        _base_lookup(),
        config_root=config_root,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    assert resolved["rate_card_id"] == "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4"

    with pytest.raises(RateCardError, match="unknown or out-of-interval rate-card key"):
        resolve_rate_card(
            _base_lookup(model_version="2026-07-29"),
            config_root=config_root,
            now=datetime(2026, 7, 29, tzinfo=timezone.utc),
        )


def test_tool_storage_and_compute_fees_preserve_exact_decimal_overflow(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    settlement = estimate_usage_cost(
        {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 10,
            "reasoning_output_tokens": 3,
        },
        rate_card_id="openai-codex-chatgpt-credit-2026-07-28-gpt-5.4",
        config_root=config_root,
        ancillary_fees={
            "tool_fees": "999999999999.1234567",
            "storage_fees": "888888888888.2345678",
            "compute_fees": "777777777777.3456789",
        },
    )

    assert settlement["exact_cost_components"]["tool_fees"] == "999999999999.1234567"
    assert settlement["exact_cost_components"]["storage_fees"] == "888888888888.2345678"
    assert settlement["exact_cost_components"]["compute_fees"] == "777777777777.3456789"


def test_multilingual_usage_records_are_language_agnostic_and_preserve_provider_fields() -> None:
    normalized = normalize_usage(
        {
            "input_tokens": 120,
            "cached_input_tokens": 20,
            "cache_write_input_tokens": 10,
            "output_tokens": 40,
            "reasoning_output_tokens": 15,
        },
        provider_native_fields={"locale": "kn-IN", "prompt_excerpt": "ನಮಸ್ಕಾರ"},
    )

    assert normalized["normalized_usage"]["uncached_input_tokens"] == 90
    assert normalized["provider_native_usage"]["locale"] == "kn-IN"


def test_context_compaction_contract_preserves_required_fields() -> None:
    payload = json.loads((TOKEN_CONFIG_ROOT / "context_compaction_contract.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "token-economics-context-compaction-contract.v1"
    assert payload["preserved_fields"] == [
        "decisions",
        "constraints",
        "unresolved_risks",
        "provenance",
        "identities",
        "required_evidence",
    ]
    assert "raw_jsonl" in payload["prohibited_recursive_inputs"]


def test_prompt_prefix_cache_policy_requires_stable_prefix_before_variable_content() -> None:
    payload = json.loads((TOKEN_CONFIG_ROOT / "prompt_cache_policy.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "token-economics-prompt-cache-policy.v1"
    assert payload["exact_prefix_matching_required"] is True
    assert payload["variable_content_must_follow_prefix"] is True
    assert payload["record_cache_hit_ratio"] is True


def test_budget_controls_are_independent_across_runtime_tools_mutations_and_cycles() -> None:
    budget = load_budget_envelope(TOKEN_CONFIG_ROOT / "budgets" / "default_stage_budget.json")
    decision = authorize_budget(
        budget,
        reserved_amount="1",
        observed_raw_input_tokens=100,
        observed_output_tokens=100,
        wall_clock_seconds=budget["wall_clock_limit_seconds"] + 1,
        tool_actions=budget["tool_action_limit"] + 1,
        tool_bytes=budget["tool_byte_limit"] + 1,
        model_turns=budget["max_model_turns"] + 1,
        repair_cycles=budget["max_repair_cycles"] + 1,
        review_cycles=budget["max_review_cycles"] + 1,
        handoffs=budget["max_handoffs"] + 1,
        mutation_paths=["workspace/secret.txt"],
        mutation_diff_bytes=budget["mutation_diff_size_limit"] + 1,
    )

    assert "economic_budget" not in decision["blocks"]
    for expected in (
        "wall_clock_limit_seconds",
        "tool_action_limit",
        "tool_byte_limit",
        "max_model_turns",
        "max_repair_cycles",
        "max_review_cycles",
        "max_handoffs",
        "mutations",
        "mutation_diff_size_limit",
    ):
        assert expected in decision["blocks"]


def test_concurrent_ledger_writes_aggregate_deterministically(tmp_path: Path) -> None:
    ledger = LedgerStore(tmp_path / "ledger.jsonl")

    def _append(index: int) -> None:
        ledger.append(
            {
                "provider_turn_id": f"turn-{index:03d}",
                "accepted_outcome": index % 2 == 0,
                "retry_count": 1,
                "duration_ms": 10 + index,
                "settlement": {"rounded_amount": "1.0000000"},
            }
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_append, range(20)))

    summary = summarize_ledger(ledger.read_all())
    assert summary["record_count"] == 20
    assert summary["attempt_cost_total"] == "20.0000000"
    assert summary["retry_count_total"] == 20


def test_unknown_usage_is_never_zero() -> None:
    normalized = normalize_usage(
        {
            "input_tokens": "UNKNOWN",
            "cached_input_tokens": "UNKNOWN",
            "cache_write_input_tokens": "UNKNOWN",
            "output_tokens": "UNKNOWN",
            "reasoning_output_tokens": "UNKNOWN",
        }
    )

    assert normalized["normalized_usage"]["status"] == "UNKNOWN"
    assert normalized["normalized_usage"]["total_input_tokens"] == "UNKNOWN"
    assert normalized["normalized_usage"]["total_output_tokens"] == "UNKNOWN"


def test_reconciliation_variance_and_staleness_are_reported(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
    stale = resolve_rate_card(_base_lookup(), config_root=config_root, now=datetime(2028, 8, 1, tzinfo=timezone.utc))
    reconciliation = reconcile_records(
        {
            "estimate": {"rounded_amount": "1.0000000"},
            "observed": {"rounded_amount": "2.0000000"},
            "settled": {"rounded_amount": "2.5000000"},
            "provider_ids": {"provider_turn_id": "turn-variance-001"},
        }
    )

    assert stale["stale"] is True
    assert reconciliation["variance_amount"] == "0.5000000"
