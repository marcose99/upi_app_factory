from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from tools.transformation_controller import phase46a

SCHEMA_VERSION = 1
DEFAULT_POLICY = Path("policies/autonomous_execution_policy.json")


class ExecutionPolicyError(RuntimeError):
    """Raised when a deterministic execution policy boundary is crossed."""


@dataclass(frozen=True)
class CandidateEdit:
    path: str
    size_before: int
    sha256_before: str
    sha256_after: str
    replacement_counts: dict[str, int]


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_policy(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_POLICY
    raw_policy: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_policy, dict):
        raise ExecutionPolicyError("Phase 46B policy must be a JSON object")
    payload: dict[str, Any] = {
        str(key): value for key, value in raw_policy.items()
    }
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ExecutionPolicyError("Unsupported Phase 46B policy schema")
    llm_policy = payload.get("llm")
    if not isinstance(llm_policy, dict) or llm_policy.get("enabled") is not False:
        raise ExecutionPolicyError("Phase 46B requires LLM execution to remain disabled")
    protected_actions = payload.get("protected_actions")
    if (
        not isinstance(protected_actions, dict)
        or protected_actions.get("allow") != []
    ):
        raise ExecutionPolicyError("Protected actions must have an empty allow-list")
    return payload


def normalized_relative(path_text: str) -> PurePosixPath:
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ExecutionPolicyError(f"Unsafe repository path: {path_text}")
    return relative


def is_excluded(path_text: str, prefixes: Sequence[str]) -> bool:
    return any(
        path_text == prefix.rstrip("/") or path_text.startswith(prefix)
        for prefix in prefixes
    )


def discover_branding_candidates(
    root: Path,
    findings: Sequence[phase46a.Finding],
    policy: dict[str, Any],
    max_files_override: int | None = None,
) -> list[CandidateEdit]:
    branding = policy["safe_branding_batch"]
    allowed_categories = set(branding["allowed_categories"])
    allowed_classifications = set(branding["allowed_classifications"])
    allowed_suffixes = set(branding["allowed_suffixes"])
    excluded_prefixes = tuple(branding["excluded_prefixes"])
    replacements: dict[str, str] = branding["replacements"]
    max_file_bytes = int(branding["max_file_bytes"])
    max_total_bytes = int(branding["max_total_bytes"])
    configured_max_files = int(branding["max_files"])
    max_files = (
        configured_max_files
        if max_files_override is None
        else min(configured_max_files, max_files_override)
    )

    eligible_paths = sorted(
        {
            item.path
            for item in findings
            if item.category in allowed_categories
            and item.classification in allowed_classifications
        }
    )

    candidates: list[CandidateEdit] = []
    total_bytes = 0
    for path_text in eligible_paths:
        relative = normalized_relative(path_text)
        if is_excluded(path_text, excluded_prefixes):
            continue
        if relative.suffix.lower() not in allowed_suffixes:
            continue
        path = root.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        if size > max_file_bytes:
            raise ExecutionPolicyError(
                f"Safe branding candidate exceeds per-file limit: {path_text}"
            )
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExecutionPolicyError(
                f"Safe branding candidate is not UTF-8: {path_text}"
            ) from exc

        updated = text
        counts: dict[str, int] = {}
        for source, destination in replacements.items():
            count = updated.count(source)
            if count:
                counts[source] = count
                updated = updated.replace(source, destination)
        if not counts or updated == text:
            continue

        updated_data = updated.encode("utf-8")
        total_bytes += size
        candidates.append(
            CandidateEdit(
                path=path_text,
                size_before=size,
                sha256_before=sha256_bytes(data),
                sha256_after=sha256_bytes(updated_data),
                replacement_counts=counts,
            )
        )

    if len(candidates) > max_files:
        raise ExecutionPolicyError(
            f"Safe branding batch has {len(candidates)} files; limit is {max_files}"
        )
    if total_bytes > max_total_bytes:
        raise ExecutionPolicyError(
            f"Safe branding batch has {total_bytes} bytes; limit is {max_total_bytes}"
        )
    return candidates


class CheckpointLedger:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.checkpoint_dir = run_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.event_ledger = run_dir / "execution_events.jsonl"
        self.previous_hash = "GENESIS"
        self.sequence = 0

    def append(
        self,
        stage: str,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        self.sequence += 1
        payload = {
            "schema_version": SCHEMA_VERSION,
            "sequence": self.sequence,
            "recorded_at": phase46a.utc_now(),
            "stage": stage,
            "status": status,
            "details": details,
            "previous_checkpoint_hash": self.previous_hash,
        }
        checkpoint_hash = sha256_bytes(canonical_json(payload))
        record = {**payload, "checkpoint_hash": checkpoint_hash}
        phase46a.write_json(
            self.checkpoint_dir / f"{self.sequence:03d}_{stage.lower()}.json",
            record,
        )
        with self.event_ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        self.previous_hash = checkpoint_hash
        return record


def verify_checkpoint_chain(run_dir: Path) -> dict[str, Any]:
    previous = "GENESIS"
    checked = 0
    for path in sorted((run_dir / "checkpoints").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        checkpoint_hash = record.pop("checkpoint_hash")
        if record["previous_checkpoint_hash"] != previous:
            raise ExecutionPolicyError(f"Broken checkpoint predecessor: {path.name}")
        expected = sha256_bytes(canonical_json(record))
        if checkpoint_hash != expected:
            raise ExecutionPolicyError(f"Checkpoint hash mismatch: {path.name}")
        previous = checkpoint_hash
        checked += 1
    if checked == 0:
        raise ExecutionPolicyError("No Phase 46B checkpoints found")
    return {
        "status": "PASSED",
        "checkpoints_verified": checked,
        "final_checkpoint_hash": previous,
    }


def create_backup(
    root: Path,
    candidates: Sequence[CandidateEdit],
    run_dir: Path,
) -> tuple[Path, Path]:
    archive_path = run_dir / "safe_branding_backup.tar.gz"
    manifest_path = run_dir / "safe_branding_backup_manifest.json"
    manifest_entries: list[dict[str, Any]] = []

    with tarfile.open(archive_path, "w:gz") as archive:
        for candidate in candidates:
            relative = normalized_relative(candidate.path)
            path = root.joinpath(*relative.parts)
            archive.add(path, arcname=candidate.path, recursive=False)
            manifest_entries.append(
                {
                    "path": candidate.path,
                    "size": path.stat().st_size,
                    "mode": stat.S_IMODE(path.stat().st_mode),
                    "sha256": phase46a.sha256_file(path),
                }
            )

    phase46a.write_json(
        manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": phase46a.utc_now(),
            "archive": archive_path.name,
            "archive_sha256": phase46a.sha256_file(archive_path),
            "files": manifest_entries,
        },
    )
    return archive_path, manifest_path


def apply_candidates(
    root: Path,
    candidates: Sequence[CandidateEdit],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    replacements: dict[str, str] = policy["safe_branding_batch"]["replacements"]
    applied: list[dict[str, Any]] = []

    for candidate in candidates:
        relative = normalized_relative(candidate.path)
        path = root.joinpath(*relative.parts)
        original_mode = stat.S_IMODE(path.stat().st_mode)
        before = path.read_bytes()
        if sha256_bytes(before) != candidate.sha256_before:
            raise ExecutionPolicyError(
                f"Candidate changed after planning: {candidate.path}"
            )
        text = before.decode("utf-8")
        updated = text
        for source, destination in replacements.items():
            updated = updated.replace(source, destination)
        after = updated.encode("utf-8")
        if sha256_bytes(after) != candidate.sha256_after:
            raise ExecutionPolicyError(
                f"Candidate transformation is not deterministic: {candidate.path}"
            )

        temporary = path.with_name(f".{path.name}.phase46b.tmp")
        temporary.write_bytes(after)
        os.chmod(temporary, original_mode)
        temporary.replace(path)
        applied.append(
            {
                **asdict(candidate),
                "size_after": len(after),
                "mode": oct(original_mode),
            }
        )
    return applied


def restore_backup(root: Path, run_dir: Path) -> list[str]:
    manifest = json.loads(
        (run_dir / "safe_branding_backup_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    archive_path = run_dir / manifest["archive"]
    if phase46a.sha256_file(archive_path) != manifest["archive_sha256"]:
        raise ExecutionPolicyError("Backup archive hash mismatch")

    allowed = {item["path"]: item for item in manifest["files"]}
    restored: list[str] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        member_names = {member.name for member in members if member.isfile()}
        if member_names != set(allowed):
            raise ExecutionPolicyError("Backup archive paths do not match manifest")
        for member in members:
            if not member.isfile() or member.issym() or member.islnk():
                continue
            relative = normalized_relative(member.name)
            destination = root.joinpath(*relative.parts)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ExecutionPolicyError(f"Unable to restore {member.name}")
            data = extracted.read()
            expected = allowed[member.name]
            if (
                len(data) != expected["size"]
                or sha256_bytes(data) != expected["sha256"]
            ):
                raise ExecutionPolicyError(
                    f"Backup content mismatch: {member.name}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(
                f".{destination.name}.phase46b.restore"
            )
            temporary.write_bytes(data)
            os.chmod(temporary, int(expected["mode"]))
            temporary.replace(destination)
            restored.append(member.name)
    return sorted(restored)


def verify_applied_candidates(
    root: Path,
    candidates: Sequence[CandidateEdit],
    policy: dict[str, Any],
) -> dict[str, Any]:
    forbidden = tuple(policy["safe_branding_batch"]["replacements"])
    mismatches: list[dict[str, str]] = []
    for candidate in candidates:
        path = root / candidate.path
        data = path.read_bytes()
        if sha256_bytes(data) != candidate.sha256_after:
            mismatches.append(
                {"path": candidate.path, "reason": "sha256_after"}
            )
            continue
        text = data.decode("utf-8")
        remaining = [source for source in forbidden if source in text]
        if remaining:
            mismatches.append(
                {
                    "path": candidate.path,
                    "reason": "source_identity_remaining",
                }
            )
    if mismatches:
        raise ExecutionPolicyError(
            f"Applied candidate verification failed for {len(mismatches)} file(s)"
        )
    return {
        "status": "PASSED",
        "files_verified": len(candidates),
        "source_identity_remaining": 0,
    }


def validation_runtime_noise_paths(
    policy: dict[str, Any],
) -> list[str]:
    raw_paths = policy.get("validation_runtime_noise_paths", [])
    if not isinstance(raw_paths, list):
        raise ExecutionPolicyError(
            "validation_runtime_noise_paths must be a list"
        )
    normalized: list[str] = []
    for item in raw_paths:
        if not isinstance(item, str):
            raise ExecutionPolicyError(
                "validation runtime-noise paths must be strings"
            )
        normalized.append(normalized_relative(item).as_posix())
    return normalized


def restore_validation_runtime_noise(
    root: Path,
    policy: dict[str, Any],
) -> list[str]:
    paths = validation_runtime_noise_paths(policy)
    if not paths:
        return []
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "restore",
            "--source=HEAD",
            "--worktree",
            "--",
            *paths,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise ExecutionPolicyError(
            "Unable to restore validation runtime noise: "
            + completed.stdout.strip()
        )
    return paths

def validation_commands(
    python: str,
    profile: str,
) -> list[tuple[str, list[str]]]:
    if profile == "targeted":
        return [
            (
                "pytest_transformation",
                [python, "-m", "pytest", "-q", "tests/transformation"],
            ),
            (
                "ruff_transformation",
                [
                    python,
                    "-m",
                    "ruff",
                    "check",
                    "tools/transformation_controller",
                    "tests/transformation",
                ],
            ),
            (
                "mypy_transformation",
                [
                    python,
                    "-m",
                    "mypy",
                    "tools/transformation_controller",
                    "tests/transformation",
                ],
            ),
        ]
    if profile == "full":
        return [
            ("ruff_full", [python, "-m", "ruff", "check", "."]),
            ("mypy_full", [python, "-m", "mypy", "."]),
            ("pytest_full", [python, "-m", "pytest", "-q"]),
        ]
    raise ExecutionPolicyError(f"Unknown validation profile: {profile}")


def run_validations(
    root: Path,
    run_dir: Path,
    profile: str,
    log_prefix: str = "validation",
) -> dict[str, Any]:
    python = os.environ.get("UPI_APP_FACTORY_PYTHON") or shutil.which("python3")
    if not python:
        raise ExecutionPolicyError("Python executable was not resolved")
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{root}{os.pathsep}{existing}" if existing else str(root)
    )

    results: list[dict[str, Any]] = []
    for name, command in validation_commands(python, profile):
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log_name = f"{log_prefix}_{name}.log"
        phase46a.write_text(run_dir / log_name, completed.stdout)
        result = {
            "name": name,
            "command": command,
            "returncode": completed.returncode,
            "log": log_name,
        }
        results.append(result)
        if completed.returncode != 0:
            return {
                "status": "FAILED",
                "profile": profile,
                "results": results,
                "failed_command": name,
            }
    return {
        "status": "PASSED",
        "profile": profile,
        "results": results,
    }


def task_execution_decisions(
    task_graph: dict[str, Any],
    candidate_count: int,
) -> list[dict[str, Any]]:
    decisions = {
        "T-001": (
            "CONTROL_PRESENT",
            "Canonical product identity registry exists.",
        ),
        "T-002": (
            "CONTROL_PRESENT",
            "Path-neutral policy and XDG state roots exist.",
        ),
        "T-003": (
            "DEFERRED",
            "Technical Python namespace migration is reserved for a later bounded phase.",
        ),
        "T-004": (
            "AUTO_EXECUTABLE" if candidate_count else "NO_CHANGES_REQUIRED",
            "Only current display-branding findings inside the safe catalog are eligible.",
        ),
        "T-005": (
            "DEFERRED",
            "Service, container, report, and handoff identity require a separate catalog.",
        ),
        "T-006": (
            "BLOCKED_BY_DEPENDENCIES",
            "Portable checkout replay follows technical and service migration.",
        ),
        "T-007": (
            "HUMAN_GATE",
            "Local checkout and remote repository rename remain protected actions.",
        ),
    }
    result: list[dict[str, Any]] = []
    for task in task_graph["tasks"]:
        decision, reason = decisions.get(
            task["task_id"],
            ("DEFERRED", "Task is not present in the approved catalog."),
        )
        result.append(
            {
                "task_id": task["task_id"],
                "task_name": task["name"],
                "decision": decision,
                "reason": reason,
                "llm_eligible": False,
                "protected_action": (
                    bool(task["protected_action"])
                    or decision == "HUMAN_GATE"
                ),
            }
        )
    return result


def evidence_manifest(run_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "phase46b_evidence_manifest.json":
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
        "llm_calls": 0,
        "files": files,
    }


def create_review_bundle(run_dir: Path) -> Path:
    destination = (
        phase46a.export_root() / f"{run_dir.name}_review_bundle.tar.gz"
    )
    phase46a.create_bundle(run_dir, destination)
    return destination


def execute(
    root: Path,
    mode: str,
    validation_profile: str,
    max_files: int | None,
    max_repair_attempts: int,
) -> tuple[Path, Path, str]:
    root = root.resolve()
    phase46a.git(root, "rev-parse", "--git-dir")
    branch = phase46a.git(root, "branch", "--show-current")
    if branch in {"", "main"}:
        raise ExecutionPolicyError(
            "Phase 46B apply-safe execution must run in an isolated non-main branch"
        )
    if phase46a.git(root, "diff", "--cached", "--name-only"):
        raise ExecutionPolicyError("Staged changes are not permitted")

    policy = load_policy(root)
    if max_repair_attempts > int(policy["repair"]["max_attempts"]):
        raise ExecutionPolicyError("Requested repair attempts exceed policy")

    run_id = dt.datetime.now().strftime("phase46b-%Y%m%d-%H%M%S")
    run_dir = phase46a.state_root() / "execution_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ledger = CheckpointLedger(run_dir)

    run_state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "phase": "46B",
        "status": "CREATED",
        "mode": mode,
        "validation_profile": validation_profile,
        "created_at": phase46a.utc_now(),
        "updated_at": phase46a.utc_now(),
        "branch": branch,
        "head": phase46a.git(root, "rev-parse", "HEAD"),
        "llm_calls": 0,
        "protected_actions_performed": [],
        "repair_attempts": 0,
    }
    phase46a.write_json(run_dir / "run.json", run_state)
    ledger.append(
        "PREFLIGHT",
        "PASSED",
        {
            "branch": branch,
            "head": run_state["head"],
            "mode": mode,
            "llm_calls": 0,
        },
    )

    findings = phase46a.scan_patterns(root)
    task_graph = phase46a.create_task_graph(findings)
    candidates = discover_branding_candidates(
        root,
        findings,
        policy,
        max_files,
    )
    decisions = task_execution_decisions(task_graph, len(candidates))
    phase46a.write_json(
        run_dir / "task_execution_decisions.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": phase46a.utc_now(),
            "decisions": decisions,
        },
    )
    phase46a.write_json(
        run_dir / "safe_branding_candidates.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": phase46a.utc_now(),
            "candidate_count": len(candidates),
            "candidates": [asdict(item) for item in candidates],
        },
    )
    ledger.append(
        "PLAN",
        "PASSED",
        {
            "raw_findings": len(findings),
            "candidate_count": len(candidates),
            "protected_tasks_selected": 0,
        },
    )

    if mode == "rehearsal":
        final_status = "AWAITING_APPLY_SAFE_AUTHORIZATION"
        run_state.update(
            {
                "status": final_status,
                "updated_at": phase46a.utc_now(),
                "candidate_count": len(candidates),
            }
        )
        phase46a.write_json(run_dir / "run.json", run_state)
        ledger.append("FINALIZE", final_status, {"changes_applied": 0})
        phase46a.write_json(
            run_dir / "checkpoint_verification.json",
            verify_checkpoint_chain(run_dir),
        )
        phase46a.write_json(
            run_dir / "phase46b_evidence_manifest.json",
            evidence_manifest(run_dir),
        )
        bundle = create_review_bundle(run_dir)
        return run_dir, bundle, final_status

    if mode != "apply-safe":
        raise ExecutionPolicyError(f"Unsupported execution mode: {mode}")

    if not candidates:
        validation = run_validations(
            root,
            run_dir,
            validation_profile,
        )
        restore_validation_runtime_noise(root, policy)
        if validation["status"] != "PASSED":
            raise ExecutionPolicyError(
                "Validation failed with no safe changes applied"
            )
        phase46a.write_json(run_dir / "validation_report.json", validation)
        final_status = "NO_CHANGES_COMPLETED"
        run_state.update(
            {
                "status": final_status,
                "updated_at": phase46a.utc_now(),
                "candidate_count": 0,
                "changes_retained": 0,
            }
        )
        phase46a.write_json(run_dir / "run.json", run_state)
        ledger.append(
            "VALIDATE",
            "PASSED",
            {"profile": validation_profile},
        )
        ledger.append("FINALIZE", final_status, {"changes_applied": 0})
        phase46a.write_json(
            run_dir / "checkpoint_verification.json",
            verify_checkpoint_chain(run_dir),
        )
        phase46a.write_json(
            run_dir / "phase46b_evidence_manifest.json",
            evidence_manifest(run_dir),
        )
        bundle = create_review_bundle(run_dir)
        return run_dir, bundle, final_status

    archive_path, manifest_path = create_backup(root, candidates, run_dir)
    ledger.append(
        "BACKUP",
        "PASSED",
        {
            "archive": archive_path.name,
            "manifest": manifest_path.name,
            "candidate_count": len(candidates),
        },
    )

    applied = apply_candidates(root, candidates, policy)
    phase46a.write_json(
        run_dir / "applied_changes.json",
        {
            "schema_version": SCHEMA_VERSION,
            "applied_at": phase46a.utc_now(),
            "files": applied,
        },
    )
    verification = verify_applied_candidates(root, candidates, policy)
    ledger.append("APPLY_SAFE", "PASSED", verification)

    validation = run_validations(
        root,
        run_dir,
        validation_profile,
        log_prefix="initial_validation",
    )
    phase46a.write_json(run_dir / "validation_report.json", validation)
    restored_validation_noise = restore_validation_runtime_noise(
        root,
        policy,
    )
    phase46a.write_json(
        run_dir / "validation_runtime_cleanup.json",
        {
            "status": "PASSED",
            "paths_restored": restored_validation_noise,
        },
    )

    if validation["status"] == "PASSED":
        final_status = "COMPLETED"
        ledger.append(
            "VALIDATE",
            "PASSED",
            {
                "profile": validation_profile,
                "changes_retained": len(candidates),
            },
        )
    else:
        ledger.append(
            "VALIDATE",
            "FAILED",
            {
                "profile": validation_profile,
                "failed_command": validation.get("failed_command"),
            },
        )
        if max_repair_attempts < 1:
            final_status = "FAILED_CLOSED"
        else:
            run_state["repair_attempts"] = 1
            restored = restore_backup(root, run_dir)
            ledger.append(
                "BOUNDED_REPAIR",
                "ROLLED_BACK",
                {
                    "repair_type": "FULL_BATCH_ROLLBACK",
                    "files_restored": len(restored),
                },
            )
            rollback_validation = run_validations(
                root,
                run_dir,
                validation_profile,
                log_prefix="rollback_validation",
            )
            phase46a.write_json(
                run_dir / "rollback_validation_report.json",
                rollback_validation,
            )
            restored_rollback_noise = restore_validation_runtime_noise(
                root,
                policy,
            )
            phase46a.write_json(
                run_dir / "rollback_runtime_cleanup.json",
                {
                    "status": "PASSED",
                    "paths_restored": restored_rollback_noise,
                },
            )
            if rollback_validation["status"] == "PASSED":
                final_status = "SAFE_ROLLBACK_COMPLETED"
                ledger.append(
                    "REVALIDATE",
                    "PASSED",
                    {
                        "profile": validation_profile,
                        "changes_retained": 0,
                    },
                )
            else:
                final_status = "FAILED_CLOSED"
                ledger.append(
                    "REVALIDATE",
                    "FAILED",
                    {
                        "profile": validation_profile,
                        "failed_command": rollback_validation.get(
                            "failed_command"
                        ),
                    },
                )

    run_state.update(
        {
            "status": final_status,
            "updated_at": phase46a.utc_now(),
            "candidate_count": len(candidates),
            "changes_retained": (
                len(candidates) if final_status == "COMPLETED" else 0
            ),
        }
    )
    phase46a.write_json(run_dir / "run.json", run_state)
    ledger.append(
        "FINALIZE",
        final_status,
        {
            "changes_retained": run_state["changes_retained"],
            "repair_attempts": run_state["repair_attempts"],
            "llm_calls": 0,
            "protected_actions_performed": [],
        },
    )
    phase46a.write_json(
        run_dir / "checkpoint_verification.json",
        verify_checkpoint_chain(run_dir),
    )
    phase46a.write_json(
        run_dir / "phase46b_evidence_manifest.json",
        evidence_manifest(run_dir),
    )
    bundle = create_review_bundle(run_dir)

    if final_status == "FAILED_CLOSED":
        raise ExecutionPolicyError(
            f"Phase 46B failed closed; evidence retained at {run_dir}"
        )
    return run_dir, bundle, final_status


def latest_run_dir() -> Path | None:
    root = phase46a.state_root() / "execution_runs"
    if not root.exists():
        return None
    runs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        reverse=True,
    )
    return runs[0] if runs else None


def command_status(run_id: str | None) -> int:
    run_dir = (
        phase46a.state_root() / "execution_runs" / run_id
        if run_id
        else latest_run_dir()
    )
    if run_dir is None or not (run_dir / "run.json").is_file():
        print("No Phase 46B execution runs found.")
        return 0
    print((run_dir / "run.json").read_text(encoding="utf-8"), end="")
    return 0


def replay(run_id: str) -> int:
    run_dir = phase46a.state_root() / "execution_runs" / run_id
    if not run_dir.is_dir():
        raise ExecutionPolicyError(f"Phase 46B run not found: {run_id}")
    checkpoint = verify_checkpoint_chain(run_dir)
    manifest = json.loads(
        (run_dir / "phase46b_evidence_manifest.json").read_text(
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
        raise ExecutionPolicyError(
            f"Phase 46B replay found {len(mismatches)} evidence mismatch(es)"
        )
    print(
        json.dumps(
            {
                "status": "PASSED",
                "run_id": run_id,
                "checkpoint_verification": checkpoint,
                "evidence_files_verified": len(manifest["files"]),
                "llm_calls": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upi-app-factory")
    subparsers = parser.add_subparsers(dest="area", required=True)
    transform = subparsers.add_parser("transform")
    actions = transform.add_subparsers(dest="action", required=True)

    execute_parser = actions.add_parser("execute")
    execute_parser.add_argument("--project-root", default=".")
    execute_parser.add_argument(
        "--mode",
        choices=("rehearsal", "apply-safe"),
        default="rehearsal",
    )
    execute_parser.add_argument(
        "--validation-profile",
        choices=("targeted", "full"),
        default="full",
    )
    execute_parser.add_argument("--max-files", type=int)
    execute_parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=1,
    )

    status_parser = actions.add_parser("execution-status")
    status_parser.add_argument("--run-id")

    replay_parser = actions.add_parser("replay")
    replay_parser.add_argument("--run-id", required=True)

    arguments = parser.parse_args(argv)
    if arguments.action == "execute":
        run_dir, bundle, status = execute(
            Path(arguments.project_root),
            arguments.mode,
            arguments.validation_profile,
            arguments.max_files,
            arguments.max_repair_attempts,
        )
        print(f"Phase 46B execution created: {run_dir}")
        print(f"Review bundle: {bundle}")
        print(f"Execution status: {status}")
        print("LLM calls: 0")
        print("Protected actions performed: none")
        return 0
    if arguments.action == "execution-status":
        return command_status(arguments.run_id)
    if arguments.action == "replay":
        return replay(arguments.run_id)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

