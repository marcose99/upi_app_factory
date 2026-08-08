#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_RELATIVE_PATH = (
    "factory_governance/current_contracts/current_operational_contract.json"
)
GENERIC_CONTRACT_RELATIVE_PATH = (
    "factory_governance/current_contracts/upi_factory_contract.json"
)
APPLICATION_PROFILE_PREFIX = "factory_governance/current_contracts/application_profiles"
REGISTRY_PATH = PROJECT_ROOT / REGISTRY_RELATIVE_PATH

SECRET_PATTERNS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret =",
    "client_secret:",
    "api_key =",
    "api_key:",
    "secret_key =",
    "secret_key:",
    "password =",
)

EXECUTABLE_RELEASE_PATTERNS = (
    r"\bgit\s+push\b",
    r"\bgit\s+tag\b",
    r"\bgit\s+merge\b",
    r"\bnpm\s+publish\b",
)

EXECUTABLE_LIVE_CALL_PATTERNS = (
    r"\brequests\.",
    r"\burllib\.request\b",
    r"\bhttpx\.(get|post|put|delete|patch|stream)\(",
    r"\bboto3\b",
    r"\bgoogle\.cloud\b",
    r"\bazure\.",
    r"\bstripe\b",
    r"\brazorpay\b",
)

APPLICATION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"contract must be a JSON object: {path}")
    return payload


def _validated_repo_relative_path(
    relative: str,
    *,
    required_prefix: str | None = None,
    must_exist: bool = True,
    require_file: bool = True,
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("repository-relative path must be a non-empty string")
    if "\\" in relative or "\x00" in relative:
        raise ValueError(f"invalid repository-relative path: {relative}")

    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"unsafe repository-relative path: {relative}")

    if required_prefix is not None:
        prefix = PurePosixPath(required_prefix)
        if posix.parts[: len(prefix.parts)] != prefix.parts:
            raise ValueError(
                f"repository-relative path is outside required prefix "
                f"{required_prefix}: {relative}"
            )

    root = PROJECT_ROOT.resolve()
    target = (PROJECT_ROOT / Path(*posix.parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"repository-relative path escapes project root: {relative}") from exc

    if must_exist:
        if require_file and not target.is_file():
            raise ValueError(f"required repository file is missing: {relative}")
        if not require_file and not target.exists():
            raise ValueError(f"required repository path is missing: {relative}")
    return target


def repository_file(relative: str, *, required_prefix: str | None = None) -> Path:
    return _validated_repo_relative_path(
        relative,
        required_prefix=required_prefix,
        must_exist=True,
        require_file=True,
    )


def load_contract_registry() -> dict[str, Any]:
    payload = _load_json(REGISTRY_PATH)
    if payload.get("schema_version") != "upi-app-factory.current-contract-registry.v1":
        raise ValueError("unsupported current contract registry schema")

    generic_path = payload.get("generic_upi_factory_contract")
    if generic_path != GENERIC_CONTRACT_RELATIVE_PATH:
        raise ValueError("registry generic contract path is not canonical")
    repository_file(GENERIC_CONTRACT_RELATIVE_PATH)

    profiles = payload.get("application_profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("application_profiles must be a non-empty list")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(profiles):
        if not isinstance(item, dict):
            raise ValueError(f"application profile registry entry {index} must be an object")
        application_id = item.get("application_id")
        if not isinstance(application_id, str) or not APPLICATION_ID_RE.fullmatch(
            application_id
        ):
            raise ValueError(f"invalid application_id in registry entry {index}")
        if application_id in seen_ids:
            raise ValueError(f"duplicate application profile id: {application_id}")
        seen_ids.add(application_id)

        relative = item.get("path")
        expected = f"{APPLICATION_PROFILE_PREFIX}/{application_id}.json"
        if relative != expected:
            raise ValueError(
                f"application profile path must be canonical for {application_id}: {relative}"
            )
        if relative in seen_paths:
            raise ValueError(f"duplicate application profile path: {relative}")
        seen_paths.add(relative)
        repository_file(relative, required_prefix=APPLICATION_PROFILE_PREFIX)

        if item.get("status") != "CURRENT_AND_VERIFIED":
            raise ValueError(
                f"application profile registry entry is not CURRENT_AND_VERIFIED: "
                f"{application_id}"
            )
    return payload


def registered_application_ids(
    registry: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    current = registry or load_contract_registry()
    profiles = current.get("application_profiles")
    if not isinstance(profiles, list):
        raise ValueError("application_profiles must be a list")
    ids: list[str] = []
    for item in profiles:
        if not isinstance(item, dict):
            raise ValueError("application profile registry entry must be an object")
        application_id = item.get("application_id")
        if not isinstance(application_id, str):
            raise ValueError("application profile id must be a string")
        ids.append(application_id)
    return tuple(ids)


def load_generic_upi_factory_contract() -> dict[str, Any]:
    load_contract_registry()
    payload = _load_json(repository_file(GENERIC_CONTRACT_RELATIVE_PATH))
    if payload.get("schema_version") != "upi-app-factory.generic-upi-factory-contract.v1":
        raise ValueError("unsupported generic UPI factory contract schema")
    return payload


def load_application_profile(application_id: str) -> dict[str, Any]:
    if not APPLICATION_ID_RE.fullmatch(application_id):
        raise ValueError(f"invalid application profile id: {application_id}")

    registry = load_contract_registry()
    profiles = registry.get("application_profiles")
    if not isinstance(profiles, list):
        raise ValueError("application_profiles must be a list")
    matches = [
        item
        for item in profiles
        if isinstance(item, dict) and item.get("application_id") == application_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one application profile for {application_id}")
    relative = matches[0].get("path")
    if not isinstance(relative, str):
        raise ValueError(f"profile path is missing for {application_id}")
    payload = _load_json(
        repository_file(relative, required_prefix=APPLICATION_PROFILE_PREFIX)
    )
    if payload.get("schema_version") != "upi-app-factory.application-profile.v1":
        raise ValueError("unsupported application profile schema")
    if payload.get("application_id") != application_id:
        raise ValueError("application profile identity mismatch")
    if payload.get("inherits_generic_contract") != GENERIC_CONTRACT_RELATIVE_PATH:
        raise ValueError("application profile generic-contract inheritance mismatch")
    return payload


def load_registered_application_profiles() -> dict[str, dict[str, Any]]:
    registry = load_contract_registry()
    return {
        application_id: load_application_profile(application_id)
        for application_id in registered_application_ids(registry)
    }


def recipient_test_command(
    application_id: str,
    profile: dict[str, Any] | None = None,
) -> str:
    current = profile or load_application_profile(application_id)
    recipient = current.get("recipient_test")
    if not isinstance(recipient, dict):
        raise ValueError("recipient_test must be an object")
    value = recipient.get("rendered_shell_command")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("recipient test command must be a non-empty string")
    return value


def required_local_run_environment(
    application_id: str,
    profile: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    current = profile or load_application_profile(application_id)
    values = current.get("local_acceptance_environment")
    if not isinstance(values, list) or not values:
        raise ValueError("local acceptance environment must be a non-empty list")

    result: list[str] = []
    keys: set[str] = set()
    for value in values:
        if not isinstance(value, str) or "\n" in value or "=" not in value:
            raise ValueError(
                "local acceptance environment must contain KEY=value strings only"
            )
        key, _, _ = value.partition("=")
        if not key or key in keys:
            raise ValueError(f"duplicate or empty local acceptance environment key: {key}")
        keys.add(key)
        result.append(value)
    return tuple(result)


def find_secret_like_text(text: str) -> list[str]:
    return [pattern for pattern in SECRET_PATTERNS if pattern in text]


def find_executable_boundary_violations(text: str) -> list[str]:
    violations: list[str] = []
    for pattern in (*EXECUTABLE_RELEASE_PATTERNS, *EXECUTABLE_LIVE_CALL_PATTERNS):
        if re.search(pattern, text):
            violations.append(pattern)
    if ".zip" in text:
        violations.append(".zip")
    return violations


def documentation_discussion_is_safe(text: str) -> bool:
    return not find_secret_like_text(text)


def assert_required_strings(
    text: str,
    values: Iterable[str],
    label: str,
) -> list[str]:
    errors: list[str] = []
    for value in values:
        if value not in text:
            errors.append(f"{label} missing contract value: {value}")
    return errors
