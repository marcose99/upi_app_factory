from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from factory.operator_portal.token_economics_dashboard import build_dashboard
from factory.native_capability_prerun.engine import PreRunConfig, build_payloads
from factory.token_economics import (
    ArtifactOwnershipError,
    LedgerStore,
    RateCardError,
    authorize_budget,
    build_token_economics_summary,
    load_budget_envelope,
    redacted_evidence_report,
    resolve_rate_card,
    validate_artifact_path,
)


ROOT = Path(__file__).resolve().parents[1]
FAILED_DEBIT_FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


def _copy_token_config(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return tmp_path / "config" / "token_economics"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    material = {key: value for key, value in payload.items() if key != "integrity"}
    payload["integrity"] = {
        "sha256": hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_budget_controls_keep_economic_and_raw_token_limits_independent() -> None:
    budget = load_budget_envelope(ROOT / "config" / "token_economics" / "budgets" / "default_stage_budget.json")

    raw_block = authorize_budget(
        budget,
        reserved_amount="10",
        observed_raw_input_tokens=budget["raw_input_anomaly_limit"] + 1,
        observed_output_tokens=100,
    )
    economic_block = authorize_budget(
        budget,
        reserved_amount="181",
        observed_raw_input_tokens=100,
        observed_output_tokens=100,
    )

    assert "raw_input_anomaly_limit" in raw_block["blocks"]
    assert "economic_budget" not in raw_block["blocks"]
    assert "economic_budget" in economic_block["blocks"]
    assert "raw_input_anomaly_limit" not in economic_block["blocks"]


def test_rate_card_resolution_flags_staleness_and_rejects_overlapping_intervals(tmp_path: Path) -> None:
    config_root = _copy_token_config(tmp_path)
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

    stale = resolve_rate_card(lookup, config_root=config_root, now=datetime(2028, 8, 1, tzinfo=timezone.utc))
    assert stale["stale"] is True

    overlap_path = config_root / "rate_cards" / "chatgpt_credit" / "overlap.json"
    payload = json.loads(
        (config_root / "rate_cards" / "chatgpt_credit" / "openai-codex-chatgpt-credit-2026-07-28-gpt-5.4.json").read_text(
            encoding="utf-8"
        )
    )
    payload["rate_card_id"] = "openai-codex-chatgpt-credit-overlap"
    payload["effective_from"] = "2026-07-28T12:00:00Z"
    _write_json(overlap_path, payload)

    with pytest.raises(RateCardError, match="overlapping effective intervals"):
        resolve_rate_card(lookup, config_root=config_root, now=datetime(2026, 7, 29, tzinfo=timezone.utc))


def test_ledger_duplicate_guard_and_compact_redaction_fail_closed(tmp_path: Path) -> None:
    ledger = LedgerStore(tmp_path / "ledger.jsonl")
    written = ledger.append(
        {
            "provider_turn_id": "turn-001",
            "settlement": {"rounded_amount": "1.2500000"},
            "accepted_outcome": True,
        }
    )
    assert written["provider_turn_id"] == "turn-001"

    with pytest.raises(RuntimeError, match="duplicate ledger identity rejected"):
        ledger.append({"provider_turn_id": "turn-001"})

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
    compact_record = report["records"][0]
    assert "prompt" not in compact_record
    assert "response" not in compact_record
    assert "reasoning" not in compact_record
    assert compact_record["prompt_size_bytes"] > 0
    assert compact_record["response_sha256"]


def test_dashboard_rollups_expose_stage_run_application_and_outcome_views(tmp_path: Path) -> None:
    _copy_token_config(tmp_path)
    ledger = LedgerStore(tmp_path / "workspace" / "token_economics_runtime" / "ledger.jsonl")
    ledger.append(
        {
            "stage_id": "plan",
            "run_id": "run-001",
            "application_id": "upi_dispute_resolution",
            "accepted_outcome": True,
            "duration_ms": 25,
            "retry_count": 0,
            "estimate": {"rounded_amount": "0.5000000"},
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
            "reconciliation": {"status": "RECONCILIATION_PENDING"},
        }
    )
    ledger.append(
        {
            "stage_id": "review",
            "run_id": "run-002",
            "application_id": "upi_dispute_resolution",
            "accepted_outcome": False,
            "duration_ms": 50,
            "retry_count": 1,
            "normalized_usage": {
                "status": "OBSERVED",
                "total_input_tokens": 80,
                "cache_read_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "uncached_input_tokens": 80,
                "total_output_tokens": 40,
                "reasoning_output_tokens": 20,
            },
            "settlement": {"rounded_amount": "1.2500000"},
            "reconciliation": {"status": "RECONCILED"},
        }
    )

    dashboard = build_dashboard(tmp_path)

    assert dashboard["status"] == "available"
    assert dashboard["aggregations"]["overall"]["record_count"] == 2
    assert dashboard["aggregations"]["per_stage"]["plan"]["record_count"] == 1
    assert dashboard["aggregations"]["per_run"]["run-002"]["retry_count_total"] == 1
    assert dashboard["aggregations"]["per_application"]["upi_dispute_resolution"]["record_count"] == 2
    assert dashboard["aggregations"]["per_outcome"]["accepted"]["record_count"] == 1
    assert dashboard["aggregations"]["per_outcome"]["rejected"]["record_count"] == 1
    assert dashboard["reconciliation"]["unresolved_records"] == 1
    assert dashboard["usage_views"]["observed"]["status"] == "RECORDED"


def test_summary_and_dashboard_expose_operator_visibility_contracts() -> None:
    summary = build_token_economics_summary(ROOT)
    dashboard = build_dashboard(ROOT)

    assert summary["operator_visibility"] == {
        "estimate_vs_observed_vs_settled": True,
        "token_breakdown": True,
        "budget_vs_runtime_controls": True,
        "aggregation_levels": ["per_stage", "per_run", "per_application", "per_outcome"],
        "cost_per_accepted_outcome": True,
        "reconciliation_variance": True,
    }
    assert summary["default_stage_budget"]["budget_id"] == "governed-local-stage-default"
    assert dashboard["schema_version"] == "token-economics-operator-surface.v1"
    assert dashboard["usage_views"]["estimate"]["status"] == "NOT_RECORDED"
    assert dashboard["budget_controls"]["blocked_next_call"] is False
    assert dashboard["aggregations"]["per_stage"] == {}


def test_factoryctl_normalize_contract_is_available_offline(tmp_path: Path) -> None:
    payload_path = tmp_path / "usage.json"
    payload_path.write_text(
        json.dumps(
            {
                "usage": {
                    "input_tokens": 120,
                    "cached_input_tokens": 20,
                    "cache_write_input_tokens": 10,
                    "output_tokens": 40,
                    "reasoning_output_tokens": 15,
                },
                "provider_request_id": "req-local-001",
            }
        ),
        encoding="utf-8",
    )

    current_pythonpath = os.environ.get("PYTHONPATH")
    completed = subprocess.run(
        [str(ROOT / "factoryctl"), "token-economics", "normalize", str(payload_path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src")
            if not current_pythonpath
            else str(ROOT / "src") + os.pathsep + current_pythonpath,
        },
    )

    assert completed.returncode == 0, completed.stdout
    payload = json.loads("\n".join(line for line in completed.stdout.splitlines() if not line.startswith("+ ")))
    assert payload["provider_request_id"] == "req-local-001"
    assert payload["normalized_usage"]["uncached_input_tokens"] == 90
    assert payload["normalized_usage"]["reasoning_output_tokens"] == 15


def test_native_prerun_uses_explicit_source_requirement_proof_and_typed_evidence(tmp_path: Path) -> None:
    payloads = build_payloads(
        PreRunConfig(
            requirements_document=FAILED_DEBIT_FIXTURE,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "native_prerun",
            factory_root=ROOT,
        )
    )

    structured_item = next(
        item
        for item in payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]["items"]
        if item.get("source_requirement_id") == "UC-001"
    )

    assert structured_item["proof_mode"] == "source_requirement_id"
    assert structured_item["matched_capabilities"] == [
        {
            "id": "CAP-FAILED-DEBIT-DOMAIN",
            "description": (
                "Failed debit dispute domain rules, state transitions, evidence completeness, "
                "audit, idempotency, and authorization."
            ),
        }
    ]
    assert {entry["type"] for entry in structured_item["evidence"]} >= {
        "implementation",
        "unit_test",
        "integration_test",
    }


def test_validate_artifact_path_uses_governed_registry_and_rejects_escape(tmp_path: Path) -> None:
    validated = validate_artifact_path(
        ROOT / "config" / "token_economics" / "governance_policy.json",
        project_root=ROOT,
    )
    assert validated["family_id"] == "token_economics_configuration"
    assert validated["candidate_commit_allowed"] is True

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactOwnershipError, match="artifact escaped the repository root"):
        validate_artifact_path(outside, project_root=ROOT)
