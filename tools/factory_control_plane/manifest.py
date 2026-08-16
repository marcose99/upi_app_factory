from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from tools.factory_control_plane.common import (
    ControlPlaneError,
    canonical_json,
    load_json_object,
    resolve_under_root,
    sha256_bytes,
)
from tools.factory_control_plane.lifecycle import LifecycleState, STATE_INDEX

Risk = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
ActionKind = Literal["execution", "verification", "checkpoint"]
PrerequisiteKind = Literal["file", "directory"]
RuntimeNoiseKind = Literal["file", "directory"]

TOP_LEVEL_KEYS = {
    "schema_version",
    "campaign_id",
    "metadata",
    "baseline",
    "objective",
    "scope",
    "budgets",
    "approvals",
    "validation_controls",
    "activities",
}
VALIDATION_CONTROL_KEYS = {
    "trusted_prerequisites",
    "deterministic_runtime_noise",
}
PREREQUISITE_KEYS = {"id", "kind", "path", "hydrate"}
RUNTIME_NOISE_KEYS = {"id", "kind", "path"}
ACTIVITY_KEYS = {
    "id",
    "action",
    "kind",
    "risk",
    "argv",
    "dependencies",
    "target_state",
    "timeout_seconds",
    "cwd",
    "environment_allowlist",
    "allowed_write_paths",
}
ORDERED_RISK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
PROTECTED_REPOSITORY_ROOTS = frozenset(
    {
        ".git", ".github", "config", "docs", "factory", "scripts", "src",
        "tests", "tools", "AGENTS.md",
    }
)


def _reject_protected_write_target(project_root: Path, target: Path, label: str) -> None:
    relative = target.relative_to(project_root.resolve())
    first = relative.parts[0] if relative.parts else "."
    if target == project_root.resolve() or first in PROTECTED_REPOSITORY_ROOTS:
        raise ControlPlaneError(f"{label} targets protected repository content")


def _reject_lexical_protected_target(value: str, label: str) -> None:
    first = Path(value).parts[0] if Path(value).parts else "."
    if first in PROTECTED_REPOSITORY_ROOTS:
        raise ControlPlaneError(f"{label} targets protected repository content")


@dataclass(frozen=True)
class Activity:
    id: str
    action: str
    kind: ActionKind
    risk: Risk
    argv: tuple[str, ...]
    dependencies: tuple[str, ...]
    target_state: LifecycleState
    timeout_seconds: int
    cwd: str
    environment_allowlist: tuple[str, ...]
    allowed_write_paths: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class TrustedPrerequisite:
    id: str
    kind: PrerequisiteKind
    path: str
    hydrate: bool
    digest: str


@dataclass(frozen=True)
class RuntimeNoise:
    id: str
    kind: RuntimeNoiseKind
    path: str
    digest: str


@dataclass(frozen=True)
class ValidationControls:
    trusted_prerequisites: tuple[TrustedPrerequisite, ...]
    deterministic_runtime_noise: tuple[RuntimeNoise, ...]


@dataclass(frozen=True)
class CampaignManifest:
    schema_version: int
    campaign_id: str
    metadata: dict[str, Any]
    baseline: str
    objective: str
    scope: dict[str, Any]
    budgets: dict[str, int]
    approvals: dict[str, Any]
    validation_controls: ValidationControls
    activities: tuple[Activity, ...]
    raw: dict[str, Any]
    digest: str
    path: Path


def _require_keys(payload: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise ControlPlaneError(f"{label} contains unknown fields: {sorted(unknown)}")


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ControlPlaneError(f"{key} must be a non-empty string")
    return value


def _string_tuple(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ControlPlaneError(f"{key} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or "\x00" in item or "\n" in item:
            raise ControlPlaneError(f"{key} must contain safe strings")
        result.append(item)
    return tuple(result)


def _topological(activities: tuple[Activity, ...]) -> None:
    by_id = {activity.id: activity for activity in activities}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(activity_id: str) -> None:
        if activity_id in visiting:
            raise ControlPlaneError("activity dependency cycle detected")
        if activity_id in visited:
            return
        visiting.add(activity_id)
        for dependency in by_id[activity_id].dependencies:
            if dependency not in by_id:
                raise ControlPlaneError(f"unknown dependency {dependency}")
            visit(dependency)
        visiting.remove(activity_id)
        visited.add(activity_id)

    for activity in activities:
        visit(activity.id)


def _validate_monotonic_targets(activities: tuple[Activity, ...]) -> None:
    by_id = {activity.id: activity for activity in activities}
    for activity in activities:
        for dependency in activity.dependencies:
            if (
                STATE_INDEX[activity.target_state]
                < STATE_INDEX[by_id[dependency].target_state]
            ):
                raise ControlPlaneError(
                    "activity target states must be monotonic across dependencies"
                )


def _parse_validation_controls(
    raw: dict[str, Any],
    project_root: Path,
) -> ValidationControls:
    controls = raw.get("validation_controls", {})
    if not isinstance(controls, dict):
        raise ControlPlaneError("validation_controls must be an object")
    _require_keys({str(k): v for k, v in controls.items()}, VALIDATION_CONTROL_KEYS, "validation_controls")
    prerequisites = _parse_prerequisites(controls.get("trusted_prerequisites", []), project_root)
    noise = _parse_runtime_noise(controls.get("deterministic_runtime_noise", []), project_root)
    return ValidationControls(
        trusted_prerequisites=prerequisites,
        deterministic_runtime_noise=noise,
    )


def _parse_prerequisites(
    value: object,
    project_root: Path,
) -> tuple[TrustedPrerequisite, ...]:
    if not isinstance(value, list):
        raise ControlPlaneError("trusted_prerequisites must be a list")
    seen: set[str] = set()
    prerequisites: list[TrustedPrerequisite] = []
    for item in value:
        if not isinstance(item, dict):
            raise ControlPlaneError("trusted prerequisite must be an object")
        _require_keys({str(k): v for k, v in item.items()}, PREREQUISITE_KEYS, "trusted prerequisite")
        prerequisite_id = _string(item, "id")
        if prerequisite_id in seen:
            raise ControlPlaneError(f"duplicate trusted prerequisite id {prerequisite_id}")
        seen.add(prerequisite_id)
        kind = _string(item, "kind")
        if kind not in {"file", "directory"}:
            raise ControlPlaneError(f"unknown trusted prerequisite kind {kind}")
        path = _string(item, "path")
        resolve_under_root(project_root, path)
        hydrate = item.get("hydrate", False)
        if not isinstance(hydrate, bool):
            raise ControlPlaneError("trusted prerequisite hydrate must be a boolean")
        if hydrate:
            _reject_lexical_protected_target(path, "hydrated prerequisite")
        item_dict = {str(k): v for k, v in item.items()}
        prerequisites.append(
            TrustedPrerequisite(
                id=prerequisite_id,
                kind=cast(PrerequisiteKind, kind),
                path=path,
                hydrate=hydrate,
                digest=sha256_bytes(canonical_json(item_dict)),
            )
        )
    return tuple(prerequisites)


def _parse_runtime_noise(value: object, project_root: Path) -> tuple[RuntimeNoise, ...]:
    if not isinstance(value, list):
        raise ControlPlaneError("deterministic_runtime_noise must be a list")
    seen: set[str] = set()
    result: list[RuntimeNoise] = []
    for item in value:
        if not isinstance(item, dict):
            raise ControlPlaneError("deterministic runtime noise must be an object")
        _require_keys({str(k): v for k, v in item.items()}, RUNTIME_NOISE_KEYS, "deterministic runtime noise")
        noise_id = _string(item, "id")
        if noise_id in seen:
            raise ControlPlaneError(f"duplicate deterministic runtime noise id {noise_id}")
        seen.add(noise_id)
        kind = _string(item, "kind")
        if kind not in {"file", "directory"}:
            raise ControlPlaneError(f"unknown deterministic runtime noise kind {kind}")
        path = _string(item, "path")
        resolve_under_root(project_root, path)
        item_dict = {str(k): v for k, v in item.items()}
        result.append(
            RuntimeNoise(
                id=noise_id,
                kind=cast(RuntimeNoiseKind, kind),
                path=path,
                digest=sha256_bytes(canonical_json(item_dict)),
            )
        )
    return tuple(result)


def load_manifest(path: Path, project_root: Path) -> CampaignManifest:
    raw = load_json_object(path)
    _require_keys(raw, TOP_LEVEL_KEYS, "manifest")
    if raw.get("schema_version") != 1:
        raise ControlPlaneError("schema_version must be 1")
    campaign_id = _string(raw, "campaign_id")
    metadata = raw.get("metadata")
    scope = raw.get("scope")
    budgets = raw.get("budgets")
    approvals = raw.get("approvals")
    activities_raw = raw.get("activities")
    if (
        not isinstance(metadata, dict)
        or not isinstance(scope, dict)
        or not isinstance(approvals, dict)
    ):
        raise ControlPlaneError("metadata, scope and approvals must be objects")
    if not isinstance(budgets, dict):
        raise ControlPlaneError("budgets must be an object")
    parsed_budgets: dict[str, int] = {}
    for key, value in budgets.items():
        if not isinstance(key, str) or not isinstance(value, int) or value < 0 or value > 10_000:
            raise ControlPlaneError("budget bounds are invalid")
        parsed_budgets[key] = value
    if not isinstance(activities_raw, list) or not activities_raw:
        raise ControlPlaneError("activities must be a non-empty list")
    allowed_scope = _string_tuple(scope.get("allowed_write_paths", []), "scope.allowed_write_paths")
    for scope_path in allowed_scope:
        resolve_under_root(project_root, scope_path)
    validation_controls = _parse_validation_controls(raw, project_root)
    scope_roots = tuple(resolve_under_root(project_root, value) for value in allowed_scope)
    for noise_control in validation_controls.deterministic_runtime_noise:
        resolved = resolve_under_root(project_root, noise_control.path)
        if not scope_roots or not any(
            resolved == root or resolved.is_relative_to(root) for root in scope_roots
        ):
            raise ControlPlaneError(
                f"deterministic runtime noise is outside manifest scope: {noise_control.path}"
            )
    for prerequisite_control in validation_controls.trusted_prerequisites:
        if prerequisite_control.hydrate:
            resolved = resolve_under_root(project_root, prerequisite_control.path)
            _reject_protected_write_target(
                project_root, resolved, "hydrated prerequisite"
            )
            if not scope_roots or not any(
                resolved == root or resolved.is_relative_to(root) for root in scope_roots
            ):
                raise ControlPlaneError(
                    f"hydrated prerequisite is outside manifest scope: {prerequisite_control.path}"
                )
    seen: set[str] = set()
    activities: list[Activity] = []
    for item in activities_raw:
        if not isinstance(item, dict):
            raise ControlPlaneError("activity must be an object")
        _require_keys({str(k): v for k, v in item.items()}, ACTIVITY_KEYS, "activity")
        activity_id = _string(item, "id")
        if activity_id in seen:
            raise ControlPlaneError(f"duplicate activity id {activity_id}")
        seen.add(activity_id)
        risk = _string(item, "risk")
        if risk not in ORDERED_RISK:
            raise ControlPlaneError(f"unknown risk {risk}")
        kind = _string(item, "kind")
        if kind not in {"execution", "verification", "checkpoint"}:
            raise ControlPlaneError(f"unknown activity kind {kind}")
        target_text = _string(item, "target_state")
        try:
            target = LifecycleState(target_text)
        except ValueError as exc:
            raise ControlPlaneError(f"unknown target state {target_text}") from exc
        timeout = item.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout < 1 or timeout > 3600:
            raise ControlPlaneError("timeout_seconds must be 1..3600")
        cwd = _string(item, "cwd")
        resolve_under_root(project_root, cwd)
        writes = _string_tuple(item.get("allowed_write_paths"), "allowed_write_paths")
        for write_path in writes:
            resolved = resolve_under_root(project_root, write_path)
            if allowed_scope and not any(
                resolved == resolve_under_root(project_root, p)
                or resolved.is_relative_to(resolve_under_root(project_root, p))
                for p in allowed_scope
            ):
                raise ControlPlaneError(
                    f"write path is outside manifest scope: {write_path}"
                )
        env_allow = _string_tuple(item.get("environment_allowlist"), "environment_allowlist")
        argv = _string_tuple(item.get("argv"), "argv")
        if kind == "verification" and writes:
            raise ControlPlaneError("verification activities may not declare write paths")
        activity_dict = {str(k): v for k, v in item.items()}
        activities.append(
            Activity(
                id=activity_id,
                action=_string(item, "action"),
                kind=cast(ActionKind, kind),
                risk=cast(Risk, risk),
                argv=argv,
                dependencies=_string_tuple(
                    item.get("dependencies"),
                    "dependencies",
                ),
                target_state=target,
                timeout_seconds=timeout,
                cwd=cwd,
                environment_allowlist=env_allow,
                allowed_write_paths=writes,
                digest=sha256_bytes(canonical_json(activity_dict)),
            )
        )
    result = tuple(activities)
    _topological(result)
    _validate_monotonic_targets(result)
    return CampaignManifest(
        schema_version=1,
        campaign_id=campaign_id,
        metadata={str(k): v for k, v in metadata.items()},
        baseline=_string(raw, "baseline"),
        objective=_string(raw, "objective"),
        scope={str(k): v for k, v in scope.items()},
        budgets=parsed_budgets,
        approvals={str(k): v for k, v in approvals.items()},
        validation_controls=validation_controls,
        activities=result,
        raw=raw,
        digest=sha256_bytes(canonical_json(raw)),
        path=path.resolve(),
    )
