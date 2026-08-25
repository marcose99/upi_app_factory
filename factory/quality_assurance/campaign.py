"""Provider-neutral, local-only Wave-1 assurance campaign entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Sequence
import zipfile

from . import (
    QualityAssuranceError,
    build_factory_quality_bundle,
    finalize_internal_review_acceptance,
    validate_quality_bundle,
)
from .kernel import canonical_bytes


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_zip(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def _contracts(args: argparse.Namespace) -> dict[str, Any]:
    names = (
        "acceptance_contract",
        "test_contract",
        "claim_contract",
        "report_contract",
        "review_contract",
    )
    result = {}
    for name in names:
        value = getattr(args, name)
        if not value:
            raise QualityAssuranceError(f"--{name.replace('_', '-')} is required")
        result[name] = _load(Path(value))
    return result


def run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    contracts = _contracts(args)
    checkpoint, output = Path(args.checkpoint_dir).resolve(), Path(args.output_dir).resolve()
    manifest_path = checkpoint / "wave1_campaign.json"
    if not manifest_path.is_file():
        candidates = sorted(checkpoint.glob("*WAVE1_MANIFEST.json"))
        if len(candidates) != 1:
            raise QualityAssuranceError("checkpoint must contain exactly one Wave-1 manifest")
        manifest_path = candidates[0]
    manifest = _load(manifest_path)
    applications = manifest.get("applications", [])
    if not isinstance(applications, list) or len(applications) != 8:
        raise QualityAssuranceError("checkpoint must identify exactly eight applications")
    scenario_ids = [str(row.get("scenario_id", "")) for row in applications]
    if "" in scenario_ids or len(set(scenario_ids)) != 8:
        raise QualityAssuranceError("eight distinct scenario IDs are required")
    if not manifest.get("factory_raw_measures"):
        raise QualityAssuranceError(
            "checkpoint manifest is authenticated but has no qualification measures; "
            "regeneration must supply executable Lane-A results before acceptance"
        )
    output.mkdir(parents=True, exist_ok=True)
    factory_bundle = build_factory_quality_bundle(
        output_dir=output / "factory",
        claims=manifest.get("factory_claims", []),
        evidence=manifest.get("factory_evidence", []),
        raw_measures=manifest.get("factory_raw_measures", {}),
        sections=manifest.get("factory_report_sections", []),
    )
    package_rows, decisions, fingerprints = [], [], {}
    for record in applications:
        scenario = str(record["scenario_id"])
        source = checkpoint / str(record.get("source_path", ""))
        if not source.is_dir():
            raise QualityAssuranceError(f"application source missing: {scenario}")
        app_target = output / "applications" / scenario
        shutil.copytree(source, app_target / "package", dirs_exist_ok=False)
        from . import build_application_quality_bundle

        bundle = build_application_quality_bundle(
            output_dir=app_target,
            claims=record.get("claims", []),
            evidence=record.get("evidence", []),
            raw_measures=record.get("raw_measures", {}),
            sections=record.get("report_sections", []),
        )
        validate_quality_bundle(bundle, root=app_target)
        package_path = app_target / "package.zip"
        package_digest = _safe_zip(app_target / "package", package_path)
        package_rows.append(
            {
                "scenario_id": scenario,
                "path": package_path.relative_to(output).as_posix(),
                "sha256": package_digest,
            }
        )
        decision = dict(bundle["acceptance"])
        decision["scenario_id"] = scenario
        decisions.append(decision)
        fingerprint = str(record.get("semantic_fingerprint", ""))
        if len(fingerprint) != 64:
            raise QualityAssuranceError(f"invalid semantic fingerprint: {scenario}")
        fingerprints[scenario] = fingerprint
    if len(set(fingerprints.values())) != 8:
        raise QualityAssuranceError("scenario semantic fingerprints must be distinct")
    reviews = manifest.get("internal_reviews", [])
    review_decision = finalize_internal_review_acceptance(reviews)
    review_packet = {
        "schema_version": "upi-app-factory.review-packet.v1",
        **review_decision,
        "roles": reviews,
        "external_roles": contracts["review_contract"].get("external_human_roles", []),
    }
    (output / "review_packet.json").write_bytes(canonical_bytes(review_packet))
    external_dir = Path(tempfile.mkdtemp(prefix="upi-review-"))
    try:
        (external_dir / "review_packet.json").write_bytes(canonical_bytes(review_packet))
        external_zip = output / "external_human_review_packet.zip"
        _safe_zip(external_dir, external_zip)
    finally:
        shutil.rmtree(external_dir)
    portfolio = {
        "schema_version": "upi-app-factory.portfolio-acceptance.v1",
        "factory": factory_bundle["acceptance"],
        "applications": decisions,
        **review_decision,
        "scenario_semantic_fingerprints": fingerprints,
        "application_packages": package_rows,
        "external_human_review_packet": "external_human_review_packet.zip",
    }
    (output / "portfolio_acceptance.json").write_bytes(canonical_bytes(portfolio))
    return portfolio


def finalize_reviews(args: argparse.Namespace) -> dict[str, Any]:
    output, reviews_dir = Path(args.output_dir), Path(args.reviews_dir)
    reports = [_load(path) for path in sorted(reviews_dir.glob("*.json"))]
    decision = finalize_internal_review_acceptance(reports)
    (output / "internal_review_acceptance.json").write_bytes(canonical_bytes(decision))
    return decision


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--acceptance-contract")
    parser.add_argument("--test-contract")
    parser.add_argument("--claim-contract")
    parser.add_argument("--report-contract")
    parser.add_argument("--review-contract")
    parser.add_argument("--finalize-internal-reviews", action="store_true")
    parser.add_argument("--reviews-dir")
    args = parser.parse_args(argv)
    result = finalize_reviews(args) if args.finalize_internal_reviews else run_campaign(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
