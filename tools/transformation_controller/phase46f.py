from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
CANONICAL_DISPLAY_NAME = "UPI App Factory"
EXPECTED_LEGACY_DISPLAY_NAMES = {
    "FactoryFromNothing",
    "UPI Dispute Resolution Factory",
}
REGISTRY_PATH = Path("config/compatibility_aliases.json")
RUNTIME_PATH = Path("config/identity_compatibility_runtime.json")
CONTRACT_PATH = Path("config/display_identity_contract.json")
POLICY_PATH = Path("policies/display_identity_migration_policy.json")


class DisplayIdentityMigrationError(RuntimeError):
    """Raised when the bounded display migration contract is violated."""


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DisplayIdentityMigrationError(
            f"{label} must be a JSON object"
        )
    return {str(key): value for key, value in raw.items()}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def display_aliases(
    registry: dict[str, Any],
) -> list[dict[str, str]]:
    raw_aliases = registry.get("aliases")
    if not isinstance(raw_aliases, list):
        raise DisplayIdentityMigrationError(
            "Compatibility registry aliases must be a list"
        )

    result: list[dict[str, str]] = []
    for raw_alias in raw_aliases:
        if not isinstance(raw_alias, dict):
            raise DisplayIdentityMigrationError(
                "Compatibility alias must be an object"
            )
        alias_type = raw_alias.get("alias_type")
        if alias_type != "display_identity":
            continue
        alias_id = raw_alias.get("alias_id")
        legacy = raw_alias.get("legacy")
        canonical = raw_alias.get("canonical")
        status = raw_alias.get("status")
        removal = raw_alias.get("removal")
        if (
            not isinstance(alias_id, str)
            or not isinstance(legacy, str)
            or not isinstance(canonical, str)
            or not isinstance(status, str)
            or not isinstance(removal, str)
        ):
            raise DisplayIdentityMigrationError(
                "Display alias fields must be strings"
            )
        result.append(
            {
                "alias_id": alias_id,
                "legacy": legacy,
                "canonical": canonical,
                "status": status,
                "removal": removal,
            }
        )

    result.sort(key=lambda item: item["alias_id"])
    return result


def validate_source_registry(
    registry: dict[str, Any],
) -> list[dict[str, str]]:
    aliases = display_aliases(registry)
    if len(aliases) != 2:
        raise DisplayIdentityMigrationError(
            "Exactly two governed display aliases are required"
        )
    legacy_names = {item["legacy"] for item in aliases}
    if legacy_names != EXPECTED_LEGACY_DISPLAY_NAMES:
        raise DisplayIdentityMigrationError(
            "Unexpected governed legacy display identities"
        )
    if {
        item["canonical"] for item in aliases
    } != {CANONICAL_DISPLAY_NAME}:
        raise DisplayIdentityMigrationError(
            "Display aliases must share the canonical display identity"
        )
    if any(
        item["removal"] != "HUMAN_APPROVAL_REQUIRED"
        for item in aliases
    ):
        raise DisplayIdentityMigrationError(
            "Display aliases must retain human-approved removal"
        )
    return aliases


def build_contract(
    registry: dict[str, Any],
) -> dict[str, Any]:
    aliases = validate_source_registry(registry)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "46F",
        "contract_id": "upi-app-factory-display-identity-v1",
        "canonical_display_identity": {
            "name": CANONICAL_DISPLAY_NAME,
            "write_status": "REQUIRED",
        },
        "accepted_legacy_display_identities": [
            {
                "alias_id": item["alias_id"],
                "name": item["legacy"],
                "read_status": "ACCEPTED_FOR_COMPATIBILITY",
                "write_status": "PROHIBITED",
                "removal": "HUMAN_APPROVAL_REQUIRED",
            }
            for item in aliases
        ],
        "read_posture": "CANONICAL_AND_GOVERNED_LEGACY_ACCEPTED",
        "write_posture": "CANONICAL_ONLY",
        "compatibility_layer": "RETAINED",
        "technical_identifier_migration": "NOT_PERFORMED",
        "physical_checkout_rename": "NOT_PERFORMED",
        "remote_repository_rename": "NOT_PERFORMED",
        "historical_evidence_rewrite": "PROHIBITED",
        "certification_posture": "CERTIFICATION_READY_NOT_CERTIFIED",
        "llm_calls": 0,
    }


def updated_registry(
    registry: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(registry)
    raw_aliases = result.get("aliases")
    if not isinstance(raw_aliases, list):
        raise DisplayIdentityMigrationError(
            "Compatibility registry aliases must be a list"
        )
    updated = 0
    for raw_alias in raw_aliases:
        if (
            isinstance(raw_alias, dict)
            and raw_alias.get("alias_type") == "display_identity"
        ):
            raw_alias["status"] = (
                "CONTRACT_ACTIVE_COMPATIBILITY_RETAINED"
            )
            raw_alias["contract"] = CONTRACT_PATH.as_posix()
            updated += 1
    if updated != 2:
        raise DisplayIdentityMigrationError(
            "Exactly two display aliases must be activated"
        )
    result["phase"] = "46F"
    result["display_contract_status"] = "ACTIVE"
    return result


def updated_runtime(
    runtime: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(runtime)
    result["phase"] = "46F"
    result["display_identity_contract"] = CONTRACT_PATH.as_posix()
    result["display_read_posture"] = (
        "CANONICAL_AND_GOVERNED_LEGACY_ACCEPTED"
    )
    result["display_write_posture"] = "CANONICAL_ONLY"
    result["compatibility_layer"] = "RETAINED"
    result["compatibility_removal_requires_human_approval"] = True
    return result


def verify_contract(root: Path) -> dict[str, Any]:
    root = root.resolve()
    registry = load_object(root / REGISTRY_PATH, "Alias registry")
    runtime = load_object(root / RUNTIME_PATH, "Compatibility runtime")
    contract = load_object(root / CONTRACT_PATH, "Display contract")
    policy = load_object(root / POLICY_PATH, "Migration policy")

    aliases = validate_source_registry(registry)
    if contract != build_contract(registry):
        raise DisplayIdentityMigrationError(
            "Display identity contract does not match the registry"
        )

    if registry.get("phase") != "46F":
        raise DisplayIdentityMigrationError(
            "Alias registry phase must be 46F"
        )
    if registry.get("display_contract_status") != "ACTIVE":
        raise DisplayIdentityMigrationError(
            "Alias registry display contract must be active"
        )
    if any(
        item["status"]
        != "CONTRACT_ACTIVE_COMPATIBILITY_RETAINED"
        for item in aliases
    ):
        raise DisplayIdentityMigrationError(
            "Display alias compatibility status is not active"
        )

    if runtime.get("phase") != "46F":
        raise DisplayIdentityMigrationError(
            "Compatibility runtime phase must be 46F"
        )
    if runtime.get("display_identity_contract") != (
        CONTRACT_PATH.as_posix()
    ):
        raise DisplayIdentityMigrationError(
            "Runtime display contract pointer is incorrect"
        )
    if runtime.get("display_write_posture") != "CANONICAL_ONLY":
        raise DisplayIdentityMigrationError(
            "Runtime must emit only the canonical display identity"
        )
    if runtime.get("compatibility_layer") != "RETAINED":
        raise DisplayIdentityMigrationError(
            "Compatibility layer must remain retained"
        )

    if policy.get("schema_version") != SCHEMA_VERSION:
        raise DisplayIdentityMigrationError(
            "Unsupported display migration policy schema"
        )
    if policy.get("mode") != "CONTRACT_FIRST_BOUNDED":
        raise DisplayIdentityMigrationError(
            "Display migration policy mode is invalid"
        )
    if policy.get("legacy_alias_removal") != (
        "HUMAN_APPROVAL_REQUIRED"
    ):
        raise DisplayIdentityMigrationError(
            "Legacy alias retirement must remain human-approved"
        )
    if policy.get("physical_checkout_rename") != "PROHIBITED":
        raise DisplayIdentityMigrationError(
            "Physical checkout rename must remain prohibited"
        )
    if policy.get("remote_repository_rename") != "PROHIBITED":
        raise DisplayIdentityMigrationError(
            "Remote repository rename must remain prohibited"
        )
    if policy.get("llm_calls_allowed") != 0:
        raise DisplayIdentityMigrationError(
            "Phase 46F requires zero LLM calls"
        )

    raw_aliases = registry.get("aliases")
    if not isinstance(raw_aliases, list):
        raise DisplayIdentityMigrationError(
            "Compatibility registry aliases must be a list"
        )
    technical_aliases = [
        item
        for item in raw_aliases
        if isinstance(item, dict)
        and item.get("alias_type") == "technical_identifier"
    ]
    if (
        len(technical_aliases) != 1
        or technical_aliases[0].get("status")
        != "COMPATIBILITY_REQUIRED_BEFORE_MIGRATION"
    ):
        raise DisplayIdentityMigrationError(
            "Technical identifier migration must remain deferred"
        )

    human_gate_types = {
        item.get("alias_type")
        for item in raw_aliases
        if isinstance(item, dict)
        and item.get("status") == "HUMAN_GATE"
    }
    if human_gate_types != {"physical_path", "remote_repository"}:
        raise DisplayIdentityMigrationError(
            "Physical and remote aliases must remain human gates"
        )

    return {
        "status": "PASSED",
        "phase": "46F",
        "canonical_display_identity": CANONICAL_DISPLAY_NAME,
        "legacy_display_aliases_retained": sorted(
            EXPECTED_LEGACY_DISPLAY_NAMES
        ),
        "display_alias_count": len(aliases),
        "write_posture": "CANONICAL_ONLY",
        "read_posture": (
            "CANONICAL_AND_GOVERNED_LEGACY_ACCEPTED"
        ),
        "compatibility_layer": "RETAINED",
        "technical_identifier_migration": "NOT_PERFORMED",
        "physical_checkout_rename": "NOT_PERFORMED",
        "remote_repository_rename": "NOT_PERFORMED",
        "repository_mutations_outside_candidate": 0,
        "llm_calls": 0,
    }


def implement(root: Path) -> dict[str, Any]:
    root = root.resolve()
    registry = load_object(root / REGISTRY_PATH, "Alias registry")
    runtime = load_object(root / RUNTIME_PATH, "Compatibility runtime")
    validate_source_registry(registry)
    write_json(root / REGISTRY_PATH, updated_registry(registry))
    write_json(root / RUNTIME_PATH, updated_runtime(runtime))
    refreshed_registry = load_object(
        root / REGISTRY_PATH,
        "Alias registry",
    )
    write_json(root / CONTRACT_PATH, build_contract(refreshed_registry))
    return verify_contract(root)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "transform":
        arguments = arguments[1:]

    parser = argparse.ArgumentParser(
        prog="upi-app-factory transform",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    implement_parser = actions.add_parser(
        "implement-display-identity-contract"
    )
    implement_parser.add_argument("--project-root", default=".")

    verify_parser = actions.add_parser(
        "verify-display-identity-contract"
    )
    verify_parser.add_argument("--project-root", default=".")

    status_parser = actions.add_parser("display-identity-status")
    status_parser.add_argument("--project-root", default=".")

    parsed = parser.parse_args(arguments)
    root = Path(parsed.project_root).resolve()

    if parsed.action == "implement-display-identity-contract":
        result = implement(root)
    else:
        result = verify_contract(root)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
