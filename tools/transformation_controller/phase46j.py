from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EVIDENCE_INPUTS = (
    "config/display_identity_contract.json",
    "config/path_identity_contract.json",
    "config/technical_identity_contract.json",
    "config/compatibility_aliases.json",
    "config/technical_namespace_aliases.json",
    "config/identity_compatibility_runtime.json",
)


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def digest_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_evidence_index(project_root: Path) -> dict[str, Any]:
    records = []
    for relative in EVIDENCE_INPUTS:
        path = project_root / relative
        if not path.is_file():
            raise ValueError(f"Required migration evidence input is missing: {relative}")
        record = digest_file(path)
        record["path"] = relative
        records.append(record)
    return {
        "schema_version": 1,
        "phase": "46J",
        "status": "PASSED",
        "evidence_records": records,
        "evidence_record_count": len(records),
        "llm_calls": 0,
    }


def verify_readiness(project_root: Path) -> dict[str, Any]:
    readiness = load_object(
        project_root / "config/identity_migration_readiness.json",
        "Identity migration readiness",
    )
    evidence = load_object(
        project_root
        / "evidence/phase46j/identity_migration_evidence_index.json",
        "Identity migration evidence index",
    )
    policy = load_object(
        project_root / "policies/identity_migration_evidence_policy.json",
        "Identity migration evidence policy",
    )

    expected_controls = {
        "display_identity_contract": "COMPLETE",
        "path_neutral_runtime": "COMPLETE",
        "technical_namespace_compatibility": "COMPLETE",
        "physical_checkout_rename": "DEFERRED_HUMAN_GATE",
        "remote_repository_rename": "DEFERRED_HUMAN_GATE",
        "legacy_alias_retirement": "DEFERRED_HUMAN_GATE",
        "formal_certification": "NOT_PERFORMED",
    }
    controls = readiness.get("controls")
    if controls != expected_controls:
        raise ValueError("Identity migration readiness controls are unexpected")
    if readiness.get("certification_posture") != (
        "CERTIFICATION_READY_NOT_CERTIFIED"
    ):
        raise ValueError("Certification posture is incorrect")
    if policy.get("official_certification_claim_allowed") is not False:
        raise ValueError("Official certification claims must be prohibited")
    if evidence.get("status") != "PASSED":
        raise ValueError("Migration evidence index did not pass")

    regenerated = build_evidence_index(project_root)
    if regenerated["evidence_records"] != evidence.get("evidence_records"):
        raise ValueError("Migration evidence hashes do not replay")

    return {
        "status": "PASSED",
        "phase": "46J",
        "controls": expected_controls,
        "evidence_record_count": regenerated["evidence_record_count"],
        "certification_posture": "CERTIFICATION_READY_NOT_CERTIFIED",
        "physical_checkout_rename": "NOT_PERFORMED",
        "remote_repository_rename": "NOT_PERFORMED",
        "legacy_aliases_retained": True,
        "llm_calls": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Phase 46J migration evidence closure"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    report = verify_readiness(parsed.project_root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
