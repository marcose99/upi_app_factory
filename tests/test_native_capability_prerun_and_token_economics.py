from __future__ import annotations

from pathlib import Path

from factory.native_capability_prerun.engine import (
    PreRunConfig,
    build_payloads,
    extract_text,
    inventory_obligations,
)
from factory.token_economics import estimate_usage_cost, normalize_usage


ROOT = Path(__file__).resolve().parents[1]
FAILED_DEBIT_FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


def test_inventory_uses_structured_descriptions_without_promoting_metadata_names() -> None:
    text = extract_text(FAILED_DEBIT_FIXTURE)["text"]
    obligations = inventory_obligations(text, application_id="upi_dispute_resolution")

    obligation_texts = {item["text"] for item in obligations}
    assert "app_id: upi_app_factory" not in obligation_texts
    assert "product_name: UPI App Factory" not in obligation_texts
    assert "Payer" not in obligation_texts
    assert all(not text.startswith("source requirement id ") for text in obligation_texts)

    actor_obligation = next(
        item for item in obligations if item.get("source_requirement_id") == "ACT-001"
    )
    assert actor_obligation["source_requirement_name"] == "Payer"
    assert actor_obligation["text"].startswith("Fictional customer reporting a debit")


def test_build_payloads_proves_current_fixture_and_carries_source_requirement_ids(
    tmp_path: Path,
) -> None:
    payloads = build_payloads(
        PreRunConfig(
            requirements_document=FAILED_DEBIT_FIXTURE,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "native_prerun",
            factory_root=ROOT,
        )
    )

    report = payloads["CAPABILITY_PRE_RUN_REPORT.json"]
    matrix = payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]
    improvements = payloads["FACTORY_IMPROVEMENT_REQUIREMENTS.json"]

    assert report["decision"] == "PROVEN_100_PERCENT_CAPABILITY"
    assert report["mandatory_gate_passed"] is True
    assert report["requirements_path"] == FAILED_DEBIT_FIXTURE.relative_to(ROOT).as_posix()
    assert not Path(report["requirements_path"]).is_absolute()
    assert improvements["items"] == []
    structured_item = next(
        item for item in matrix["items"] if item.get("source_requirement_id") == "UC-001"
    )
    assert structured_item["source_requirement_name"] == "Lodge failed debit case"
    assert structured_item["classification"] == "FULFILLABLE"


def test_unsupported_structured_requirement_maps_improvement_to_source_requirement_id(
    tmp_path: Path,
) -> None:
    requirements = tmp_path / "unsupported.md"
    requirements.write_text(
        """# Unsupported capability

## Use Cases
- id: UC-999; name: Quantum settlement; description: Perform quantum teleportation settlement.
""",
        encoding="utf-8",
    )

    payloads = build_payloads(
        PreRunConfig(
            requirements_document=requirements,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "unsupported_prerun",
            factory_root=ROOT,
        )
    )

    improvements = payloads["FACTORY_IMPROVEMENT_REQUIREMENTS.json"]["items"]
    report = payloads["CAPABILITY_PRE_RUN_REPORT.json"]
    assert len(improvements) == 1
    assert improvements[0]["blocked_source_requirement_ids"] == ["UC-999"]
    assert report["requirements_path"].startswith(
        f"external_requirements/{report['requirements_sha256']}/"
    )
    assert not Path(report["requirements_path"]).is_absolute()
    assert str(tmp_path) not in report["requirements_path"]


def test_token_economics_normalization_and_settlement_preserve_reasoning_subset() -> None:
    usage = {
        "input_tokens": 1200,
        "cached_input_tokens": 200,
        "cache_write_input_tokens": 100,
        "output_tokens": 300,
        "reasoning_output_tokens": 125,
    }
    normalized = normalize_usage(usage)
    assert normalized["normalized_usage"] == {
        "status": "OBSERVED",
        "total_input_tokens": 1200,
        "cache_read_input_tokens": 200,
        "cache_write_input_tokens": 100,
        "uncached_input_tokens": 900,
        "total_output_tokens": 300,
        "reasoning_output_tokens": 125,
    }

    settlement = estimate_usage_cost(
        usage,
        rate_card_id="openai-codex-chatgpt-credit-2026-07-28-gpt-5.4",
    )
    assert settlement["exact_inputs"] == {
        "uncached_input_tokens": 900,
        "cache_read_input_tokens": 200,
        "cache_write_input_tokens": 100,
        "total_output_tokens": 300,
    }
    assert settlement["state"] == "ESTIMATED"
    assert "reasoning_output_tokens" not in settlement["exact_inputs"]
    assert settlement["rounded_amount"]
