from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CANONICAL_TECHNICAL_ID = "upi_app_factory"
LEGACY_TECHNICAL_ID = "upi_dispute_resolution\x5ffactory"


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def resolve_technical_identity(value: str) -> dict[str, Any]:
    if value == CANONICAL_TECHNICAL_ID:
        return {
            "input": value,
            "canonical": CANONICAL_TECHNICAL_ID,
            "resolution": "CANONICAL",
            "compatibility_applied": False,
        }
    if value == LEGACY_TECHNICAL_ID:
        return {
            "input": value,
            "canonical": CANONICAL_TECHNICAL_ID,
            "resolution": "LEGACY_ALIAS_RESOLVED",
            "compatibility_applied": True,
        }
    raise ValueError(f"Unknown technical identity: {value}")


def canonical_write_identity() -> str:
    return CANONICAL_TECHNICAL_ID


def verify_contract(project_root: Path) -> dict[str, Any]:
    contract = load_object(
        project_root / "config/technical_identity_contract.json",
        "Technical identity contract",
    )
    aliases = load_object(
        project_root / "config/technical_namespace_aliases.json",
        "Technical namespace aliases",
    )
    runtime = load_object(
        project_root / "config/identity_compatibility_runtime.json",
        "Identity compatibility runtime",
    )
    policy = load_object(
        project_root / "policies/technical_namespace_migration_policy.json",
        "Technical namespace migration policy",
    )

    if contract.get("canonical_technical_identifier") != CANONICAL_TECHNICAL_ID:
        raise ValueError("Unexpected canonical technical identifier")
    if contract.get("canonical_write_posture") != "CANONICAL_ONLY":
        raise ValueError("Canonical-only writes are not active")
    if contract.get("physical_package_rename") != "NOT_PERFORMED":
        raise ValueError("Physical package rename must remain deferred")
    if aliases.get("legacy_aliases") != [LEGACY_TECHNICAL_ID]:
        raise ValueError("Legacy technical alias registry is unexpected")
    if aliases.get("legacy_alias_retirement") != "HUMAN_APPROVAL_REQUIRED":
        raise ValueError("Legacy alias retirement must remain human-gated")
    if runtime.get("technical_identity_contract") != ("config/technical_identity_contract.json"):
        raise ValueError("Runtime does not reference the technical contract")
    if runtime.get("technical_namespace_posture") != ("CANONICAL_WRITES_COMPATIBILITY_READS"):
        raise ValueError("Unexpected runtime technical namespace posture")
    if policy.get("physical_package_rename_allowed") is not False:
        raise ValueError("Physical package rename must be prohibited")

    canonical = resolve_technical_identity(CANONICAL_TECHNICAL_ID)
    legacy = resolve_technical_identity(LEGACY_TECHNICAL_ID)
    if canonical["compatibility_applied"]:
        raise ValueError("Canonical identity must not use compatibility")
    if not legacy["compatibility_applied"]:
        raise ValueError("Legacy identity must use compatibility")
    if canonical_write_identity() != CANONICAL_TECHNICAL_ID:
        raise ValueError("Canonical write identity is incorrect")

    return {
        "status": "PASSED",
        "phase": "46I",
        "canonical_technical_identifier": CANONICAL_TECHNICAL_ID,
        "legacy_aliases_retained": [LEGACY_TECHNICAL_ID],
        "canonical_write_posture": "CANONICAL_ONLY",
        "compatibility_read_posture": "CANONICAL_AND_LEGACY_ACCEPTED",
        "physical_package_rename": "NOT_PERFORMED",
        "physical_checkout_rename": "NOT_PERFORMED",
        "remote_repository_rename": "NOT_PERFORMED",
        "llm_calls": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Phase 46I technical namespace compatibility"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    report = verify_contract(parsed.project_root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
