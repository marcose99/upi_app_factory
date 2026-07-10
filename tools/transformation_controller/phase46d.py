from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from tools.transformation_controller import phase46a

SCHEMA_VERSION = 1
DEFAULT_REGISTRY = Path("config/compatibility_aliases.json")
DEFAULT_RUNTIME = Path("config/identity_compatibility_runtime.json")
DEFAULT_POLICY = Path("policies/compatibility_execution_policy.json")


class CompatibilityExecutionError(RuntimeError):
    """Raised when a Phase 46D compatibility boundary is crossed."""


@dataclass(frozen=True)
class ResolutionRecord:
    alias_id: str | None
    alias_type: str | None
    input_value: str
    canonical_value: str
    result: str
    compatibility_applied: bool
    requires_human_approval: bool


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CompatibilityExecutionError(
            f"{label} must be a JSON object"
        )
    return {str(key): value for key, value in raw.items()}


def load_registry(root: Path) -> dict[str, Any]:
    registry = load_object(root / DEFAULT_REGISTRY, "Alias registry")
    aliases = registry.get("aliases")
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise CompatibilityExecutionError(
            "Unsupported compatibility registry schema"
        )
    if not isinstance(aliases, list) or not aliases:
        raise CompatibilityExecutionError(
            "Compatibility aliases are required"
        )

    alias_ids: set[str] = set()
    mappings: dict[tuple[str, str], str] = {}
    for raw_alias in aliases:
        if not isinstance(raw_alias, dict):
            raise CompatibilityExecutionError(
                "Each compatibility alias must be an object"
            )
        alias_id = raw_alias.get("alias_id")
        alias_type = raw_alias.get("alias_type")
        legacy = raw_alias.get("legacy")
        canonical = raw_alias.get("canonical")
        if (
            not isinstance(alias_id, str)
            or not alias_id
            or not isinstance(alias_type, str)
            or not alias_type
            or not isinstance(legacy, str)
            or not legacy
            or not isinstance(canonical, str)
            or not canonical
        ):
            raise CompatibilityExecutionError(
                "Alias identity fields must be non-empty strings"
            )
        if alias_id in alias_ids:
            raise CompatibilityExecutionError(
                f"Duplicate alias_id: {alias_id}"
            )
        alias_ids.add(alias_id)
        key = (alias_type, legacy)
        previous = mappings.get(key)
        if previous is not None and previous != canonical:
            raise CompatibilityExecutionError(
                f"Conflicting alias mapping for {legacy}"
            )
        mappings[key] = canonical
    return registry


def load_runtime(root: Path) -> dict[str, Any]:
    runtime = load_object(
        root / DEFAULT_RUNTIME,
        "Compatibility runtime",
    )
    if runtime.get("schema_version") != SCHEMA_VERSION:
        raise CompatibilityExecutionError(
            "Unsupported compatibility runtime schema"
        )
    if runtime.get("unknown_identity_posture") != "PRESERVE":
        raise CompatibilityExecutionError(
            "Unknown identities must be preserved"
        )
    return runtime


def load_policy(root: Path) -> dict[str, Any]:
    policy = load_object(root / DEFAULT_POLICY, "Execution policy")
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise CompatibilityExecutionError(
            "Unsupported Phase 46D policy schema"
        )
    if policy.get("mode") != "state_only_additive":
        raise CompatibilityExecutionError(
            "Phase 46D must use state-only additive execution"
        )
    llm = policy.get("llm")
    if (
        not isinstance(llm, dict)
        or llm.get("enabled") is not False
        or llm.get("allowed_calls") != 0
    ):
        raise CompatibilityExecutionError(
            "Phase 46D requires zero-LLM execution"
        )
    prohibited = policy.get("prohibited_actions")
    if not isinstance(prohibited, list) or not prohibited:
        raise CompatibilityExecutionError(
            "Phase 46D prohibited actions are required"
        )
    return policy


def aliases(registry: dict[str, Any]) -> list[dict[str, Any]]:
    raw_aliases = registry["aliases"]
    result: list[dict[str, Any]] = []
    for raw_alias in raw_aliases:
        if not isinstance(raw_alias, dict):
            raise CompatibilityExecutionError(
                "Alias must be a JSON object"
            )
        result.append(
            {str(key): value for key, value in raw_alias.items()}
        )
    return result


def resolve_identity(
    registry: dict[str, Any],
    runtime: dict[str, Any],
    value: str,
    alias_type: str | None = None,
) -> ResolutionRecord:
    human_gate_types = runtime.get("human_gate_alias_types", [])
    if not isinstance(human_gate_types, list):
        raise CompatibilityExecutionError(
            "human_gate_alias_types must be a list"
        )

    for alias in aliases(registry):
        current_type = alias.get("alias_type")
        if alias_type is not None and current_type != alias_type:
            continue
        legacy = alias.get("legacy")
        canonical = alias.get("canonical")
        alias_id = alias.get("alias_id")
        if (
            not isinstance(current_type, str)
            or not isinstance(legacy, str)
            or not isinstance(canonical, str)
            or not isinstance(alias_id, str)
        ):
            raise CompatibilityExecutionError(
                "Invalid alias registry entry"
            )
        requires_human = current_type in human_gate_types
        if value == legacy:
            return ResolutionRecord(
                alias_id=alias_id,
                alias_type=current_type,
                input_value=value,
                canonical_value=canonical,
                result=(
                    "HUMAN_GATE"
                    if requires_human
                    else "ALIAS_RESOLVED"
                ),
                compatibility_applied=not requires_human,
                requires_human_approval=requires_human,
            )
        if value == canonical:
            return ResolutionRecord(
                alias_id=alias_id,
                alias_type=current_type,
                input_value=value,
                canonical_value=canonical,
                result="CANONICAL_IDENTITY",
                compatibility_applied=False,
                requires_human_approval=False,
            )

    return ResolutionRecord(
        alias_id=None,
        alias_type=alias_type,
        input_value=value,
        canonical_value=value,
        result="UNRECOGNIZED_PRESERVED",
        compatibility_applied=False,
        requires_human_approval=False,
    )


def wave_alias_types(
    policy: dict[str, Any],
    wave: str,
) -> set[str]:
    mapping = policy.get("wave_alias_types")
    if not isinstance(mapping, dict):
        raise CompatibilityExecutionError(
            "wave_alias_types must be an object"
        )
    raw_types = mapping.get(wave)
    if not isinstance(raw_types, list) or not raw_types:
        raise CompatibilityExecutionError(
            f"Unsupported or empty compatibility wave: {wave}"
        )
    result: set[str] = set()
    for item in raw_types:
        if not isinstance(item, str):
            raise CompatibilityExecutionError(
                "Wave alias types must be strings"
            )
        result.add(item)
    return result


def select_wave_aliases(
    registry: dict[str, Any],
    policy: dict[str, Any],
    wave: str,
) -> list[dict[str, Any]]:
    allowed_types = wave_alias_types(policy, wave)
    selected = [
        item
        for item in aliases(registry)
        if item.get("alias_type") in allowed_types
    ]
    selected.sort(key=lambda item: str(item["alias_id"]))
    maximum = policy.get("max_aliases_per_wave")
    if not isinstance(maximum, int) or maximum < 1:
        raise CompatibilityExecutionError(
            "max_aliases_per_wave must be positive"
        )
    if len(selected) > maximum:
        raise CompatibilityExecutionError(
            f"Wave {wave} exceeds its alias budget"
        )
    return selected


def repository_state(root: Path) -> dict[str, str]:
    status = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "-uall",
        ]
    )
    diff = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--binary",
            "--no-ext-diff",
        ]
    )
    return {
        "status_sha256": sha256_bytes(status),
        "diff_sha256": sha256_bytes(diff),
    }


def append_checkpoint(
    run_dir: Path,
    checkpoints: list[dict[str, Any]],
    name: str,
    payload: dict[str, Any],
) -> None:
    previous_hash = (
        str(checkpoints[-1]["checkpoint_hash"])
        if checkpoints
        else "GENESIS"
    )
    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "sequence": len(checkpoints) + 1,
        "name": name,
        "created_at": phase46a.utc_now(),
        "previous_hash": previous_hash,
        "payload": payload,
    }
    checkpoint["checkpoint_hash"] = sha256_bytes(
        canonical_json(checkpoint)
    )
    checkpoints.append(checkpoint)
    phase46a.write_json(
        run_dir / f"checkpoint_{len(checkpoints):03d}.json",
        checkpoint,
    )


def verify_checkpoints(run_dir: Path) -> dict[str, Any]:
    paths = sorted(
        run_dir.glob("checkpoint_[0-9][0-9][0-9].json")
    )
    previous_hash = "GENESIS"
    final_hash = previous_hash
    for expected_sequence, path in enumerate(paths, start=1):
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        recorded_hash = checkpoint.pop("checkpoint_hash")
        if checkpoint["sequence"] != expected_sequence:
            raise CompatibilityExecutionError(
                "Checkpoint sequence mismatch"
            )
        if checkpoint["previous_hash"] != previous_hash:
            raise CompatibilityExecutionError(
                "Checkpoint chain mismatch"
            )
        actual_hash = sha256_bytes(canonical_json(checkpoint))
        if actual_hash != recorded_hash:
            raise CompatibilityExecutionError(
                "Checkpoint hash mismatch"
            )
        previous_hash = recorded_hash
        final_hash = recorded_hash
    return {
        "status": "PASSED",
        "checkpoints_verified": len(paths),
        "final_checkpoint_hash": final_hash,
    }


def evidence_manifest(run_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if (
            path.is_file()
            and path.name != "phase46d_evidence_manifest.json"
        ):
            files.append(
                {
                    "path": path.relative_to(run_dir).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": phase46a.sha256_file(path),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": phase46a.utc_now(),
        "phase": "46D",
        "llm_calls": 0,
        "files": files,
    }


def execute_wave(
    root: Path,
    wave: str,
) -> tuple[Path, Path, str]:
    root = root.resolve()
    phase46a.git(root, "rev-parse", "--git-dir")
    branch = phase46a.git(root, "branch", "--show-current")
    if branch in {"", "main"}:
        raise CompatibilityExecutionError(
            "Compatibility execution requires an isolated non-main branch"
        )
    if phase46a.git(root, "diff", "--cached", "--name-only"):
        raise CompatibilityExecutionError(
            "Staged changes are not permitted during wave execution"
        )

    registry = load_registry(root)
    runtime = load_runtime(root)
    policy = load_policy(root)
    selected = select_wave_aliases(registry, policy, wave)
    before = repository_state(root)

    run_id = (
        "phase46d-"
        + wave.lower()
        + "-"
        + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    )
    run_dir = phase46a.state_root() / "compatibility_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    checkpoints: list[dict[str, Any]] = []

    append_checkpoint(
        run_dir,
        checkpoints,
        "PREFLIGHT",
        {
            "branch": branch,
            "head": phase46a.git(root, "rev-parse", "HEAD"),
            "wave": wave,
            "selected_alias_count": len(selected),
            "repository_state": before,
        },
    )

    records: list[dict[str, Any]] = []
    for alias in selected:
        legacy = alias.get("legacy")
        alias_type = alias.get("alias_type")
        if not isinstance(legacy, str) or not isinstance(
            alias_type,
            str,
        ):
            raise CompatibilityExecutionError(
                "Selected alias is malformed"
            )
        records.append(
            asdict(
                resolve_identity(
                    registry,
                    runtime,
                    legacy,
                    alias_type,
                )
            )
        )

    append_checkpoint(
        run_dir,
        checkpoints,
        "COMPATIBILITY_RESOLUTION",
        {
            "wave": wave,
            "resolution_count": len(records),
            "results": records,
        },
    )

    after = repository_state(root)
    if after != before:
        raise CompatibilityExecutionError(
            "Repository changed during state-only compatibility execution"
        )

    append_checkpoint(
        run_dir,
        checkpoints,
        "REPOSITORY_IMMUTABILITY_PROOF",
        {
            "before": before,
            "after": after,
            "unchanged": True,
        },
    )

    status = "COMPLETED" if records else "NO_ELIGIBLE_ALIASES"
    run = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "phase": "46D",
        "status": status,
        "wave": wave,
        "branch": branch,
        "created_at": phase46a.utc_now(),
        "alias_count": len(records),
        "repository_mutations": 0,
        "llm_calls": 0,
        "protected_actions_performed": [],
    }
    phase46a.write_json(run_dir / "run.json", run)
    phase46a.write_json(
        run_dir / "resolution_matrix.json",
        {
            "schema_version": SCHEMA_VERSION,
            "wave": wave,
            "records": records,
        },
    )
    phase46a.write_json(
        run_dir / "checkpoint_verification.json",
        verify_checkpoints(run_dir),
    )
    phase46a.write_json(
        run_dir / "phase46d_evidence_manifest.json",
        evidence_manifest(run_dir),
    )

    bundle = (
        phase46a.export_root() / f"{run_id}_review_bundle.tar.gz"
    )
    phase46a.create_bundle(run_dir, bundle)
    return run_dir, bundle, status


def verify_run(run_id: str) -> dict[str, Any]:
    run_dir = phase46a.state_root() / "compatibility_runs" / run_id
    if not run_dir.is_dir():
        raise CompatibilityExecutionError(
            f"Compatibility run not found: {run_id}"
        )
    manifest = json.loads(
        (run_dir / "phase46d_evidence_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    mismatches: list[str] = []
    for item in manifest["files"]:
        path = run_dir / item["path"]
        if not path.is_file():
            mismatches.append(item["path"])
            continue
        if (
            path.stat().st_size != item["size"]
            or phase46a.sha256_file(path) != item["sha256"]
        ):
            mismatches.append(item["path"])
    if mismatches:
        raise CompatibilityExecutionError(
            f"Evidence mismatch count: {len(mismatches)}"
        )
    checkpoint_result = verify_checkpoints(run_dir)
    run = json.loads(
        (run_dir / "run.json").read_text(encoding="utf-8")
    )
    if run["repository_mutations"] != 0 or run["llm_calls"] != 0:
        raise CompatibilityExecutionError(
            "Compatibility run violated execution constraints"
        )
    return {
        "status": "PASSED",
        "run_id": run_id,
        "wave": run["wave"],
        "run_status": run["status"],
        "alias_count": run["alias_count"],
        "repository_mutations": 0,
        "llm_calls": 0,
        "evidence_files_verified": len(manifest["files"]),
        "checkpoint_verification": checkpoint_result,
    }


def latest_run_dir() -> Path | None:
    root = phase46a.state_root() / "compatibility_runs"
    if not root.exists():
        return None
    runs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        reverse=True,
    )
    return runs[0] if runs else None


def status(run_id: str | None) -> int:
    run_dir = (
        phase46a.state_root() / "compatibility_runs" / run_id
        if run_id
        else latest_run_dir()
    )
    if run_dir is None or not (run_dir / "run.json").is_file():
        print("No Phase 46D compatibility runs found.")
        return 0
    print((run_dir / "run.json").read_text(encoding="utf-8"), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upi-app-factory")
    subparsers = parser.add_subparsers(dest="area", required=True)
    transform = subparsers.add_parser("transform")
    actions = transform.add_subparsers(dest="action", required=True)

    resolve_parser = actions.add_parser("resolve-identity")
    resolve_parser.add_argument("--project-root", default=".")
    resolve_parser.add_argument("--value", required=True)
    resolve_parser.add_argument("--alias-type")

    execute_parser = actions.add_parser("execute-compatibility-wave")
    execute_parser.add_argument("--project-root", default=".")
    execute_parser.add_argument("--wave", required=True)

    verify_parser = actions.add_parser("verify-compatibility-run")
    verify_parser.add_argument("--run-id", required=True)

    status_parser = actions.add_parser("compatibility-run-status")
    status_parser.add_argument("--run-id")

    arguments = parser.parse_args(argv)
    if arguments.action == "resolve-identity":
        root = Path(arguments.project_root).resolve()
        result = resolve_identity(
            load_registry(root),
            load_runtime(root),
            arguments.value,
            arguments.alias_type,
        )
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    if arguments.action == "execute-compatibility-wave":
        run_dir, bundle, run_status = execute_wave(
            Path(arguments.project_root),
            arguments.wave,
        )
        print(f"Phase 46D compatibility run created: {run_dir}")
        print(f"Review bundle: {bundle}")
        print(f"Execution status: {run_status}")
        print("Repository mutations performed: 0")
        print("LLM calls: 0")
        return 0
    if arguments.action == "verify-compatibility-run":
        print(
            json.dumps(
                verify_run(arguments.run_id),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if arguments.action == "compatibility-run-status":
        return status(arguments.run_id)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

