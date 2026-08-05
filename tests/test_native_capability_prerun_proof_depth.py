from __future__ import annotations

import json
from pathlib import Path

from factory.native_capability_prerun.engine import PreRunConfig, build_payloads


ROOT = Path(__file__).resolve().parents[1]
FAILED_DEBIT_FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


def test_fixture_frontmatter_obligations_use_exact_text_binding(tmp_path: Path) -> None:
    payloads = build_payloads(
        PreRunConfig(
            requirements_document=FAILED_DEBIT_FIXTURE,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "native_prerun",
            factory_root=ROOT,
        )
    )

    matrix_items = payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]["items"]
    runtime_item = next(item for item in matrix_items if item["text"] == "runtime_llm_calls_default: 0")

    assert runtime_item["classification"] == "FULFILLABLE"
    assert runtime_item["proof_mode"] == "exact_text"
    assert runtime_item["proof_trace"]["requirement_to_code_and_test_complete"] is True


def test_requirement_matrix_exposes_explicit_requirement_to_code_and_test_trace(tmp_path: Path) -> None:
    payloads = build_payloads(
        PreRunConfig(
            requirements_document=FAILED_DEBIT_FIXTURE,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "native_prerun",
            factory_root=ROOT,
        )
    )

    item = next(
        candidate
        for candidate in payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]["items"]
        if candidate.get("source_requirement_id") == "UC-001"
    )

    assert item["proof_trace"]["explicit_requirement_binding"] is True
    assert item["proof_trace"]["implementation_evidence"]
    assert item["proof_trace"]["automated_test_evidence"]
    assert item["proof_trace"]["requirement_to_code_and_test_complete"] is True


def test_generic_pattern_match_cannot_claim_proven_100_percent_capability(tmp_path: Path) -> None:
    requirements = tmp_path / "generic.md"
    requirements.write_text(
        "# Generic requirement\n\n- Maintain deterministic local evidence lineage.\n",
        encoding="utf-8",
    )
    catalogue_root = tmp_path / "factory"
    catalogue_root.mkdir()
    (catalogue_root / "factory").mkdir()
    (catalogue_root / "tests").mkdir()
    (catalogue_root / "factory" / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    (catalogue_root / "tests" / "test_impl.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    config_dir = catalogue_root / "config" / "native_capability"
    config_dir.mkdir(parents=True)
    (config_dir / "catalogue.json").write_text(
        json.dumps(
            {
                "schema_version": "native-capability-catalogue.v1",
                "capabilities": [
                    {
                        "id": "CAP-GENERIC",
                        "patterns": ["deterministic local evidence lineage"],
                        "evidence": [
                            {"type": "implementation", "path": "factory/impl.py"},
                            {"type": "unit_test", "path": "tests/test_impl.py"},
                        ],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payloads = build_payloads(
        PreRunConfig(
            requirements_document=requirements,
            application_id="upi_dispute_resolution",
            output_root=tmp_path / "generic_prerun",
            factory_root=catalogue_root,
        )
    )

    item = payloads["REQUIREMENT_CAPABILITY_MATRIX.json"]["items"][0]
    assert item["classification"] == "PARTIALLY_FULFILLABLE"
    assert payloads["CAPABILITY_PRE_RUN_REPORT.json"]["decision"] == "NO_GO_WITH_IMPROVEMENT_REQUIREMENTS"
