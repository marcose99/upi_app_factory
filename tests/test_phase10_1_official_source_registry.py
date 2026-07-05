from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase10_1_official_source_registry import (
    REQUIRED_ARTIFACTS,
    REQUIRED_LABELS,
    REQUIRED_SOURCE_IDS,
    generate_official_source_artifacts,
    validate_official_source_artifacts,
)


def test_phase10_1_generation_creates_all_required_artifacts(
    tmp_path: Path,
) -> None:
    written = generate_official_source_artifacts(tmp_path)

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).exists(), filename


def test_phase10_1_validation_passes_after_generation(tmp_path: Path) -> None:
    generate_official_source_artifacts(tmp_path)

    report = validate_official_source_artifacts(tmp_path)

    assert report["passed"] is True
    assert report["errors"] == []
    assert sorted(report["checked_required_labels"]) == sorted(REQUIRED_LABELS)


def test_phase10_1_registry_contains_required_sources(tmp_path: Path) -> None:
    generate_official_source_artifacts(tmp_path)
    registry = json.loads((tmp_path / "official_source_registry.json").read_text())

    source_ids = {source["source_id"] for source in registry["sources"]}

    assert set(REQUIRED_SOURCE_IDS).issubset(source_ids)


def test_phase10_1_source_claims_have_traceability(tmp_path: Path) -> None:
    generate_official_source_artifacts(tmp_path)
    registry = json.loads((tmp_path / "official_source_registry.json").read_text())
    trace = json.loads(
        (tmp_path / "source_to_requirement_traceability.json").read_text()
    )

    trace_source_ids = {row["source_id"] for row in trace["rows"]}

    for source in registry["sources"]:
        assert source["source_id"] in trace_source_ids
        assert source["extracted_claims"]
        for claim in source["extracted_claims"]:
            assert claim["claim_id"]
            assert claim["maps_to_requirement_ids"]
            assert claim["honesty_labels"]


def test_phase10_1_validation_fails_when_source_removed(tmp_path: Path) -> None:
    generate_official_source_artifacts(tmp_path)
    registry_path = tmp_path / "official_source_registry.json"
    registry = json.loads(registry_path.read_text())

    registry["sources"] = [
        source
        for source in registry["sources"]
        if source["source_id"] != "RBI_ODR_DIGITAL_PAYMENTS_2020"
    ]
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True))

    report = validate_official_source_artifacts(tmp_path)

    assert report["passed"] is False
    assert any(
        "Missing required source id: RBI_ODR_DIGITAL_PAYMENTS_2020" in error
        for error in report["errors"]
    )


def test_phase10_1_validation_blocks_false_claims(tmp_path: Path) -> None:
    generate_official_source_artifacts(tmp_path)
    policy_path = tmp_path / "source_usage_policy.md"
    policy_path.write_text(policy_path.read_text() + "\nRBI certified\n")

    report = validate_official_source_artifacts(tmp_path)

    assert report["passed"] is False
    assert any("Forbidden false claim found" in error for error in report["errors"])
