from __future__ import annotations

from factory.evidence_portability import portable_json_dumps

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence, cast

from factory.native_capability_prerun.engine import (
    GO_DECISION,
    PreRunConfig,
    run_capability_prerun,
    sha256_file,
)


AUTHORIZATION_PHRASE = "AUTHORIZE_FACTORY_SOURCE_CHANGES_FOR_EXACT_IMPROVEMENT_JSON"
PROHIBITED_ACTIONS = (
    "merge",
    "push",
    "force push",
    "tag",
    "release",
    "deployment",
    "certification claim",
    "branch deletion",
    "worktree deletion",
    "live provider calls",
)
DEFAULT_VALIDATION_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "focused_compileall",
        (
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "factory",
            "config",
            "scripts",
            "tests",
        ),
    ),
    (
        "full_compileall",
        (
            sys.executable,
            "-m",
            "compileall",
            "-q",
            ".",
        ),
    ),
)
WORKFLOW_EVIDENCE_MARKERS = (
    "full_regression",
    "capability_re_evaluation",
)


class FactoryImprovementError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImprovementWorkflowConfig:
    improvement_requirements: Path
    improvement_sha256: str
    output_root: Path
    factory_root: Path
    requirements_document: Path | None = None
    application_id: str | None = None
    plan_only: bool = True
    authorization: str | None = None
    max_repair_cycles: int = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(factory_root: Path, args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(factory_root), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(portable_json_dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(portable_json_dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_copy_tree(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise FactoryImprovementError(f"isolated workspace source must not be a symlink: {source}")
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=False)
        return
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _projection_sources(factory_root: Path) -> tuple[Path, ...]:
    candidates = (
        factory_root / "factory",
        factory_root / "config",
        factory_root / "scripts",
        factory_root / "tests",
        factory_root / "schemas",
        factory_root / "workspace" / "factory_generated" / "upi_dispute_resolution" / "generated_application",
        factory_root / "pyproject.toml",
        factory_root / "README.md",
    )
    return tuple(path for path in candidates if path.exists())


def _normalize_relative_path(value: str, *, label: str) -> str:
    candidate = Path(value.strip())
    if not value.strip():
        raise FactoryImprovementError(f"{label} must not be empty")
    if candidate.is_absolute():
        raise FactoryImprovementError(f"{label} must stay relative to the candidate root")
    normalized = candidate.as_posix().rstrip("/")
    if not normalized or normalized == ".":
        raise FactoryImprovementError(f"{label} must not point to the candidate root")
    if any(part in {"..", ""} for part in Path(normalized).parts):
        raise FactoryImprovementError(f"{label} must not escape the candidate root")
    return normalized


def _path_within_scope(path: str, scope_paths: Sequence[str]) -> bool:
    normalized = path.rstrip("/")
    for prefix in scope_paths:
        cleaned_prefix = prefix.rstrip("/")
        if normalized == cleaned_prefix or normalized.startswith(cleaned_prefix + "/"):
            return True
    return False


def _validated_command_group(value: object, *, label: str) -> list[list[str]]:
    if not isinstance(value, list) or not value:
        raise FactoryImprovementError(f"{label} must contain one or more commands")
    commands: list[list[str]] = []
    for entry in value:
        if (
            not isinstance(entry, list)
            or not entry
            or any(not isinstance(token, str) or not token for token in entry)
        ):
            raise FactoryImprovementError(f"{label} must contain non-empty string argv lists")
        commands.append(list(entry))
    return commands


def _repair_actions(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FactoryImprovementError("repair_actions must be a list")
    actions: list[dict[str, Any]] = []
    for index, entry in enumerate(value, start=1):
        if not isinstance(entry, dict):
            raise FactoryImprovementError("repair action entries must be objects")
        action_type = entry.get("type")
        path_value = entry.get("path")
        if not isinstance(action_type, str):
            raise FactoryImprovementError("repair action type must be a string")
        if not isinstance(path_value, str):
            raise FactoryImprovementError("repair action path must be a string")
        normalized_path = _normalize_relative_path(
            path_value,
            label=f"repair action {index} path",
        )
        if action_type == "write_text":
            content = entry.get("content")
            if not isinstance(content, str):
                raise FactoryImprovementError("write_text repair action requires string content")
            actions.append(
                {
                    "id": entry.get("id", f"repair_action_{index:03d}"),
                    "type": action_type,
                    "path": normalized_path,
                    "content": content,
                }
            )
            continue
        if action_type == "replace_text":
            old = entry.get("old")
            new = entry.get("new")
            if not isinstance(old, str) or not isinstance(new, str):
                raise FactoryImprovementError("replace_text repair action requires string old/new values")
            actions.append(
                {
                    "id": entry.get("id", f"repair_action_{index:03d}"),
                    "type": action_type,
                    "path": normalized_path,
                    "old": old,
                    "new": new,
                }
            )
            continue
        raise FactoryImprovementError("repair action type must be write_text or replace_text")
    return actions


def validate_improvement_payload(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FactoryImprovementError("improvement requirements must be a regular file")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise FactoryImprovementError("improvement requirements SHA-256 must be a lowercase hex digest")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise FactoryImprovementError("improvement requirements SHA-256 mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FactoryImprovementError("improvement requirements JSON must be an object")
    items = payload.get("items")
    if not isinstance(items, list):
        raise FactoryImprovementError("improvement requirements JSON must contain items")
    validated_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise FactoryImprovementError("improvement item must be an object")
        item_id = item.get("id")
        requirement = item.get("normative_requirement")
        candidate_paths = item.get("candidate_paths", [])
        if not isinstance(item_id, str) or not re.fullmatch(r"FAC-IMP-[0-9]{3}", item_id):
            raise FactoryImprovementError("improvement item id must match FAC-IMP-###")
        if not isinstance(requirement, str) or "SHALL" not in requirement:
            raise FactoryImprovementError("improvement item normative requirement must contain SHALL")
        if not isinstance(candidate_paths, list) or any(not isinstance(value, str) for value in candidate_paths):
            raise FactoryImprovementError("improvement item candidate_paths must be a string list")
        validated_items.append(
            {
                **item,
                "candidate_paths": [
                    _normalize_relative_path(value, label=f"{item_id} candidate path")
                    for value in cast(list[str], candidate_paths)
                ],
            }
        )
    validation_commands = payload.get("validation_commands")
    validated_validation_commands: dict[str, list[list[str]]] = {}
    if validation_commands is not None:
        if not isinstance(validation_commands, dict):
            raise FactoryImprovementError("validation_commands must be an object")
        validated_validation_commands = {
            "focused": _validated_command_group(
                validation_commands.get("focused"),
                label="validation_commands.focused",
            ),
            "full_regression": _validated_command_group(
                validation_commands.get("full_regression"),
                label="validation_commands.full_regression",
            ),
        }
    return {
        **payload,
        "items": validated_items,
        "repair_actions": _repair_actions(payload.get("repair_actions")),
        "validation_commands": validated_validation_commands,
    }


def _collect_authorized_scope(items: Sequence[Mapping[str, Any]]) -> list[str]:
    scope_paths = [
        path
        for item in items
        for path in cast(list[str], item.get("candidate_paths", []))
    ]
    return list(dict.fromkeys(scope_paths))


def _build_isolated_candidate(
    factory_root: Path,
    output_root: Path,
    items: Sequence[Mapping[str, Any]],
    improvement_requirements: Path,
) -> dict[str, Any]:
    isolated_root = output_root / "isolated_candidate"
    if isolated_root.exists():
        shutil.rmtree(isolated_root)
    isolated_root.mkdir(parents=True, exist_ok=False)
    copied_paths: list[str] = []
    for source in _projection_sources(factory_root):
        relative = source.relative_to(factory_root)
        _safe_copy_tree(source, isolated_root / relative)
        copied_paths.append(relative.as_posix())
    approved_items = [
        {
            "id": item["id"],
            "normative_requirement": item["normative_requirement"],
            "application_status": "APPLIED_TO_ISOLATED_CANDIDATE",
            "candidate_paths": item.get("candidate_paths", []),
        }
        for item in items
    ]
    approved_payload = {
        "schema_version": "factory-improvement-approved-items.v2",
        "source_improvement_requirements": str(improvement_requirements),
        "applied_item_count": len(approved_items),
        "items": approved_items,
    }
    write_json(isolated_root / "APPLIED_IMPROVEMENTS.json", approved_payload)
    write_json(
        isolated_root / "CANDIDATE_PROJECTION.json",
        {
            "schema_version": "factory-improvement-candidate-projection.v2",
            "copied_paths": copied_paths,
            "approved_item_ids": [item["id"] for item in items],
            "candidate_projection_sha256": canonical_sha256(approved_payload),
        },
    )
    return {
        "workspace_root": str(isolated_root),
        "copied_paths": copied_paths,
        "approved_items_path": str(isolated_root / "APPLIED_IMPROVEMENTS.json"),
        "candidate_projection_path": str(isolated_root / "CANDIDATE_PROJECTION.json"),
        "candidate_projection_sha256": canonical_sha256(approved_payload),
    }


def _run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    validation_id: str,
    timeout: int = 120,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    command_env = dict(env) if env is not None else dict(os.environ)
    pycache_root = cwd / ".pycache" / validation_id
    pycache_root.mkdir(parents=True, exist_ok=True)
    command_env["PYTHONPYCACHEPREFIX"] = str(pycache_root)
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
        env=command_env,
    )
    return {
        "validation_id": validation_id,
        "argv": list(argv),
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "status": "PASSED" if completed.returncode == 0 else "FAILED",
        "stdout_sha256": _hash_text(completed.stdout),
        "stderr_sha256": _hash_text(completed.stderr),
    }


def _run_validation_commands(candidate_root: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    command_env = {**os.environ, "PYTHONPATH": str(candidate_root)}
    for validation_id, argv in DEFAULT_VALIDATION_COMMANDS:
        reports.append(
            _run_command(
                argv,
                cwd=candidate_root,
                validation_id=validation_id,
                env=command_env,
            )
        )
    return reports


def _run_validation_group(
    candidate_root: Path,
    commands: Sequence[Sequence[str]],
    *,
    label: str,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    command_env = {**os.environ, "PYTHONPATH": str(candidate_root)}
    for index, argv in enumerate(commands, start=1):
        reports.append(
            _run_command(
                argv,
                cwd=candidate_root,
                validation_id=f"{label}_{index}",
                timeout=300,
                env=command_env,
            )
        )
    return reports


def _run_git_repo_command(
    repo_root: Path,
    args: Sequence[str],
    *,
    label: str,
) -> tuple[dict[str, Any], str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    report = {
        "validation_id": label,
        "argv": ["git", *args],
        "cwd": str(repo_root),
        "returncode": completed.returncode,
        "status": "PASSED" if completed.returncode == 0 else "FAILED",
        "stdout_sha256": _hash_text(completed.stdout),
        "stderr_sha256": _hash_text(completed.stderr),
    }
    return report, completed.stdout.strip()


def _initialize_disposable_git_repository(repo_root: Path) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for label, args in (
        ("git_init", ("init", "-q")),
        ("git_config_user_name", ("config", "user.name", "UPI App Factory Test")),
        ("git_config_user_email", ("config", "user.email", "upi-app-factory@example.invalid")),
        ("git_add_baseline", ("add", "-A")),
        ("git_commit_baseline", ("commit", "-q", "-m", "baseline")),
    ):
        report, _ = _run_git_repo_command(repo_root, args, label=label)
        reports.append(report)
        if report["status"] != "PASSED":
            raise FactoryImprovementError(f"disposable git repository setup failed at {label}")
    head_report, baseline_commit = _run_git_repo_command(
        repo_root,
        ("rev-parse", "HEAD"),
        label="git_rev_parse_baseline",
    )
    reports.append(head_report)
    if head_report["status"] != "PASSED" or not re.fullmatch(r"[0-9a-f]{40}", baseline_commit):
        raise FactoryImprovementError("disposable git repository baseline commit is unavailable")
    return {
        "git_reports": reports,
        "baseline_commit": baseline_commit,
    }


def _record_disposable_repair_commit(repo_root: Path) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    status_report, status_text = _run_git_repo_command(
        repo_root,
        ("status", "--short"),
        label="git_status_after_repair",
    )
    reports.append(status_report)
    if status_report["status"] != "PASSED":
        raise FactoryImprovementError("disposable git repository status check failed")
    if not status_text:
        return {
            "git_reports": reports,
            "candidate_commit_created": False,
            "repair_commit": None,
            "working_tree_clean": True,
        }
    for label, args in (
        ("git_add_repair", ("add", "-A")),
        ("git_commit_repair", ("commit", "-q", "-m", "authorized repair scope")),
    ):
        report, _ = _run_git_repo_command(repo_root, args, label=label)
        reports.append(report)
        if report["status"] != "PASSED":
            raise FactoryImprovementError(f"disposable repair commit failed at {label}")
    head_report, repair_commit = _run_git_repo_command(
        repo_root,
        ("rev-parse", "HEAD"),
        label="git_rev_parse_repair",
    )
    reports.append(head_report)
    if head_report["status"] != "PASSED" or not re.fullmatch(r"[0-9a-f]{40}", repair_commit):
        raise FactoryImprovementError("disposable repair commit SHA is unavailable")
    return {
        "git_reports": reports,
        "candidate_commit_created": True,
        "repair_commit": repair_commit,
        "working_tree_clean": True,
    }


def _apply_repair_actions(
    candidate_root: Path,
    actions: Sequence[Mapping[str, Any]],
    *,
    authorized_scope: Sequence[str],
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for action in actions:
        path = cast(str, action["path"])
        if not _path_within_scope(path, authorized_scope):
            raise FactoryImprovementError(f"repair action path is outside the authorized scope: {path}")
        target = candidate_root / path
        if target.exists() and target.is_symlink():
            raise FactoryImprovementError(f"repair action target must not be a symlink: {path}")
        before_exists = target.exists()
        before_sha = sha256_file(target) if target.is_file() else None
        action_type = cast(str, action["type"])
        if action_type == "write_text":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(cast(str, action["content"]), encoding="utf-8")
        elif action_type == "replace_text":
            if not target.is_file():
                raise FactoryImprovementError(f"replace_text target does not exist: {path}")
            current = target.read_text(encoding="utf-8")
            old = cast(str, action["old"])
            new = cast(str, action["new"])
            if old not in current:
                raise FactoryImprovementError(f"replace_text old value not found in {path}")
            target.write_text(current.replace(old, new), encoding="utf-8")
        else:
            raise FactoryImprovementError(f"unsupported repair action type: {action_type}")
        after_sha = sha256_file(target) if target.is_file() else None
        reports.append(
            {
                "repair_action_id": action.get("id"),
                "path": path,
                "type": action_type,
                "status": "APPLIED",
                "before_exists": before_exists,
                "before_sha256": before_sha,
                "after_sha256": after_sha,
            }
        )
    return reports


def _requirements_context_required(config: ImprovementWorkflowConfig) -> bool:
    return not config.plan_only and (
        config.requirements_document is not None or config.application_id is not None
    )


def _governed_execution_requested(config: ImprovementWorkflowConfig) -> bool:
    return (
        not config.plan_only
        and config.requirements_document is not None
        and config.application_id is not None
    )


def _outer_repo_snapshot(factory_root: Path) -> dict[str, Any]:
    return {
        "factory_head": run_git(factory_root, ["rev-parse", "HEAD"]) or "unavailable",
        "factory_branch": run_git(factory_root, ["branch", "--show-current"]) or "unknown",
        "status_sha256": _hash_text(run_git(factory_root, ["status", "--short"])),
        "diff_name_only_sha256": _hash_text(run_git(factory_root, ["diff", "--name-only"])),
        "worktree_list_sha256": _hash_text(run_git(factory_root, ["worktree", "list", "--porcelain"])),
    }


def _outer_repo_unchanged(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    return dict(before) == dict(after)


def _fulfillable_count(report: Mapping[str, Any] | None) -> int | None:
    if report is None:
        return None
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        return None
    value = summary.get("fulfillable")
    if isinstance(value, int):
        return value
    supported = summary.get("supported_count")
    if isinstance(supported, int):
        return supported
    return None


def _non_fulfillable_count(report: Mapping[str, Any] | None) -> int | None:
    if report is None:
        return None
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        return None
    value = summary.get("non_fulfillable")
    if isinstance(value, int):
        return value
    unsupported = summary.get("unsupported_count")
    partial = summary.get("partial_count")
    if isinstance(unsupported, int) and isinstance(partial, int):
        return unsupported + partial
    return None


def _capability_delta(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    *,
    approved_item_ids: Sequence[str],
) -> dict[str, Any]:
    before_decision = cast(str | None, before.get("decision") if before else None)
    after_decision = cast(str | None, after.get("decision") if after else None)
    before_fulfillable = _fulfillable_count(before)
    after_fulfillable = _fulfillable_count(after)
    before_non_fulfillable = _non_fulfillable_count(before)
    after_non_fulfillable = _non_fulfillable_count(after)
    improved = bool(
        before is not None
        and after is not None
        and (
            before_decision != after_decision
            or (before_fulfillable is not None and after_fulfillable is not None and after_fulfillable > before_fulfillable)
            or (
                before_non_fulfillable is not None
                and after_non_fulfillable is not None
                and after_non_fulfillable < before_non_fulfillable
            )
        )
    )
    return {
        "before_decision": before_decision or "not_executed",
        "after_decision": after_decision or "not_executed",
        "before_fulfillable": before_fulfillable,
        "after_fulfillable": after_fulfillable,
        "before_non_fulfillable": before_non_fulfillable,
        "after_non_fulfillable": after_non_fulfillable,
        "capability_improved": improved,
        "governed_gap_detected": bool(before is not None and before_decision != GO_DECISION),
        "unresolved_improvement_ids": list(approved_item_ids if after_decision != GO_DECISION else []),
    }


def render_execution_plan_markdown(plan: Mapping[str, Any]) -> str:
    delta = cast(Mapping[str, Any], plan["before_after_delta"])
    improvement_ids = cast(list[str], plan["approved_improvement_ids"])
    prohibited_actions = cast(list[str], plan["prohibited_actions"])
    workflow_markers = cast(Mapping[str, Mapping[str, Any]], plan["workflow_evidence_markers"])
    lines = [
        "# Factory Improvement Execution Plan",
        "",
        f"- Status: {plan['status']}",
        f"- Execution mode: {plan['execution_mode']}",
        f"- Plan only: {plan['plan_only']}",
        f"- Improvement requirements: {plan['improvement_requirements_path']}",
        f"- Improvement SHA-256: {plan['improvement_sha256']}",
        f"- Factory head: {plan['factory_head']}",
        f"- Factory branch: {plan['factory_branch']}",
        f"- Created at UTC: {plan['created_at_utc']}",
        "",
        "## Approved Improvement IDs",
        "",
    ]
    lines.extend([f"- {item_id}" for item_id in improvement_ids] or ["- None"])
    lines.extend(
        [
            "",
            "## Before/After Capability Delta",
            "",
            f"- Before decision: {delta['before_decision']}",
            f"- After decision: {delta['after_decision']}",
            f"- Before fulfillable count: {delta['before_fulfillable']}",
            f"- After fulfillable count: {delta['after_fulfillable']}",
            f"- Capability improved: {delta['capability_improved']}",
            "",
            "## Workflow Evidence Markers",
            "",
            f"- full_regression: {workflow_markers['full_regression']['status']}",
            f"- capability_re_evaluation: {workflow_markers['capability_re_evaluation']['status']}",
            "",
            "## Prohibited Actions",
            "",
        ]
    )
    lines.extend([f"- {action}" for action in prohibited_actions])
    lines.append("")
    return "\n".join(lines)


def run_factory_improvement_workflow(config: ImprovementWorkflowConfig) -> dict[str, Any]:
    output_root = config.output_root.expanduser().resolve()
    if output_root.exists() and output_root.is_symlink():
        raise FactoryImprovementError("output root must not be a symlink")
    output_root.mkdir(parents=True, exist_ok=True)

    if _requirements_context_required(config) and (
        config.requirements_document is None or config.application_id is None
    ):
        raise FactoryImprovementError(
            "requirements_document and application_id must both be supplied for governed execution"
        )

    payload = validate_improvement_payload(config.improvement_requirements.resolve(), config.improvement_sha256)
    items = cast(list[dict[str, Any]], payload.get("items", []))
    head = run_git(config.factory_root, ["rev-parse", "HEAD"]) or "unavailable"
    branch = run_git(config.factory_root, ["branch", "--show-current"]) or "unknown"
    worktree_list_sha256 = _hash_text(run_git(config.factory_root, ["worktree", "list", "--porcelain"]))
    source_change_authorized = (
        config.authorization
        == f"{AUTHORIZATION_PHRASE}:{config.improvement_sha256}"
    )
    if not config.plan_only and not source_change_authorized:
        raise FactoryImprovementError("source changes require exact improvement JSON authorization")

    isolated_candidate = _build_isolated_candidate(
        config.factory_root.resolve(),
        output_root,
        items,
        config.improvement_requirements.resolve(),
    )
    candidate_root = Path(cast(str, isolated_candidate["workspace_root"]))
    execution_mode = (
        "governed_execution"
        if _governed_execution_requested(config)
        else "compatibility_shadow_validation"
    )
    authorized_scope = _collect_authorized_scope(items)
    repair_actions = cast(list[dict[str, Any]], payload.get("repair_actions", []))
    validation_command_groups = cast(dict[str, list[list[str]]], payload.get("validation_commands", {}))

    if execution_mode == "governed_execution" and not authorized_scope:
        raise FactoryImprovementError("governed execution requires non-empty candidate_paths scope")
    if execution_mode == "governed_execution" and not repair_actions:
        raise FactoryImprovementError("governed execution requires repair_actions")
    if execution_mode == "governed_execution" and not validation_command_groups:
        raise FactoryImprovementError("governed execution requires validation_commands")

    outer_repo_before = _outer_repo_snapshot(config.factory_root.resolve())
    disposable_repo: dict[str, Any] | None = None
    repair_action_reports: list[dict[str, Any]] = []
    focused_validation_reports: list[dict[str, Any]] = []
    full_regression_reports: list[dict[str, Any]] = []
    compatibility_validation_reports: list[dict[str, Any]] = []
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    full_regression_status = "not_executed_plan_only" if config.plan_only else "not_requested"
    capability_status = "not_executed_plan_only" if config.plan_only else "not_requested"
    full_regression_executed = False
    capability_executed = False
    failure_reasons: list[str] = []

    if not config.plan_only:
        if execution_mode == "governed_execution":
            disposable_repo = _initialize_disposable_git_repository(candidate_root)
            before_root = output_root / "before_prerun"
            before = run_capability_prerun(
                PreRunConfig(
                    requirements_document=cast(Path, config.requirements_document),
                    application_id=cast(str, config.application_id),
                    output_root=before_root,
                    factory_root=config.factory_root,
                    expected_requirements_sha256=cast(str | None, payload.get("requirements_sha256")),
                )
            )
            capability_executed = True
            if before.get("decision") == GO_DECISION:
                failure_reasons.append("governed_gap_not_detected_before_repair")
            repair_action_reports = _apply_repair_actions(
                candidate_root,
                repair_actions,
                authorized_scope=authorized_scope,
            )
            repair_commit = _record_disposable_repair_commit(candidate_root)
            disposable_repo = {
                **disposable_repo,
                **repair_commit,
                "git_reports": cast(list[dict[str, Any]], disposable_repo["git_reports"])
                + cast(list[dict[str, Any]], repair_commit["git_reports"]),
            }
            if not repair_commit["candidate_commit_created"]:
                failure_reasons.append("authorized_repair_scope_produced_no_change")
            focused_validation_reports = _run_validation_group(
                candidate_root,
                validation_command_groups["focused"],
                label="focused_validation",
            )
            if all(report["status"] == "PASSED" for report in focused_validation_reports):
                full_regression_reports = _run_validation_group(
                    candidate_root,
                    validation_command_groups["full_regression"],
                    label="full_regression",
                )
                full_regression_status = (
                    "executed"
                    if all(report["status"] == "PASSED" for report in full_regression_reports)
                    else "failed"
                )
                full_regression_executed = True
            else:
                full_regression_status = "skipped_precondition_failed"
                failure_reasons.append("focused_validation_failed")
            after_root = output_root / "after_prerun"
            after = run_capability_prerun(
                PreRunConfig(
                    requirements_document=cast(Path, config.requirements_document),
                    application_id=cast(str, config.application_id),
                    output_root=after_root,
                    factory_root=candidate_root,
                    expected_requirements_sha256=cast(str | None, payload.get("requirements_sha256")),
                )
            )
            if full_regression_executed is False and not full_regression_reports:
                full_regression_reports = []
            if any(report["status"] != "PASSED" for report in focused_validation_reports):
                capability_status = "executed_after_failed_focused_validation"
            else:
                capability_status = "executed"
            if after.get("decision") != GO_DECISION:
                failure_reasons.append("after_repair_capability_not_proven")
            delta = _capability_delta(
                before,
                after,
                approved_item_ids=[item["id"] for item in items],
            )
            if not delta["capability_improved"]:
                failure_reasons.append("capability_delta_not_improved")
            if any(report["status"] != "PASSED" for report in full_regression_reports):
                failure_reasons.append("full_regression_failed")
        else:
            compatibility_validation_reports = _run_validation_commands(candidate_root)
            if any(report["status"] != "PASSED" for report in compatibility_validation_reports):
                failure_reasons.append("compatibility_validation_failed")
            full_regression_status = "compatibility_compile_only"
            capability_status = "not_requested_compatibility_path"
    else:
        delta = _capability_delta(None, None, approved_item_ids=[item["id"] for item in items])

    if not config.plan_only and execution_mode == "governed_execution":
        delta = _capability_delta(
            before,
            after,
            approved_item_ids=[item["id"] for item in items],
        )
    elif not config.plan_only:
        delta = _capability_delta(None, None, approved_item_ids=[item["id"] for item in items])

    outer_repo_after = _outer_repo_snapshot(config.factory_root.resolve())
    outer_repo_unchanged = _outer_repo_unchanged(outer_repo_before, outer_repo_after)
    if not outer_repo_unchanged:
        failure_reasons.append("active_repository_state_changed")

    validation_reports = (
        compatibility_validation_reports
        if execution_mode == "compatibility_shadow_validation"
        else focused_validation_reports + full_regression_reports
    )

    workflow_evidence_markers = {
        "full_regression": {
            "status": full_regression_status,
            "executed": full_regression_executed,
            "report_count": len(full_regression_reports),
        },
        "capability_re_evaluation": {
            "status": capability_status,
            "executed": capability_executed,
            "before_decision": before.get("decision") if before else None,
            "after_decision": after.get("decision") if after else None,
        },
    }

    protected_action_audit = {
        "schema_version": "factory-improvement-protected-action-audit.v1",
        "outer_repository_before": outer_repo_before,
        "outer_repository_after": outer_repo_after,
        "outer_repository_unchanged": outer_repo_unchanged,
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "prohibited_actions_performed": [],
    }

    bounded_repair_validation = {
        "repair_cycles_executed": len(repair_actions) if execution_mode == "governed_execution" else len(items),
        "validation_cycles_executed": len(validation_reports) + int(before is not None) + int(after is not None),
        "repeated_failure_fingerprint": (
            canonical_sha256({"failure_reasons": failure_reasons})
            if failure_reasons
            else None
        ),
    }

    status = (
        "PLAN_ONLY_READY_FOR_GOVERNED_REVIEW"
        if config.plan_only
        else "AUTHORIZED_SOURCE_CHANGE_VALIDATED"
        if not failure_reasons
        else "FACTORY_IMPROVEMENT_WORKFLOW_FAILED_CLOSED"
    )
    promotion_status = (
        "NOT_EXECUTED_PLAN_ONLY"
        if config.plan_only
        else "ELIGIBLE_NOT_PROMOTED"
        if not failure_reasons
        else "REJECTED_FAILED_CLOSED"
    )
    stopped_at = (
        "governed_review"
        if config.plan_only
        else "bounded_validation_complete"
        if not failure_reasons
        else "promotion_rejected_failed_closed"
    )

    result = {
        "schema_version": "factory-improvement-workflow.v2",
        "status": status,
        "execution_mode": execution_mode,
        "plan_only": config.plan_only,
        "promotion_status": promotion_status,
        "source_change_authorized": source_change_authorized,
        "improvement_requirements_path": str(config.improvement_requirements.resolve()),
        "improvement_sha256": config.improvement_sha256,
        "factory_head": head,
        "factory_branch": branch,
        "isolated_branch_worktree_semantics": {
            "current_branch": branch,
            "worktree_list_sha256": worktree_list_sha256,
            "merge_push_release_performed": False,
            "candidate_projection_created": True,
            "candidate_commit_created": (
                bool(disposable_repo and disposable_repo.get("candidate_commit_created"))
                if execution_mode == "governed_execution"
                else False
            ),
            "implementation_mode": (
                "isolated_disposable_git_repository"
                if execution_mode == "governed_execution"
                else "path_bounded_shadow_workspace"
            ),
            **isolated_candidate,
            **(
                {
                    "baseline_commit": disposable_repo.get("baseline_commit"),
                    "repair_commit": disposable_repo.get("repair_commit"),
                }
                if disposable_repo is not None
                else {}
            ),
        },
        "approved_improvement_ids": [item["id"] for item in items],
        "repair_scope": {
            "authorized_paths": authorized_scope,
            "repair_action_count": len(repair_actions),
        },
        "max_repair_cycles": config.max_repair_cycles,
        "bounded_repair_validation": bounded_repair_validation,
        "before_after_delta": delta,
        "workflow_evidence_markers": workflow_evidence_markers,
        "validation_reports": validation_reports,
        "focused_validation_reports": focused_validation_reports,
        "full_regression_reports": full_regression_reports,
        "compatibility_validation_reports": compatibility_validation_reports,
        "repair_action_reports": repair_action_reports,
        "capability_reports": {
            "before": before,
            "after": after,
        },
        "disposable_git_repository": disposable_repo,
        "protected_action_audit": protected_action_audit,
        "prohibited_actions": list(PROHIBITED_ACTIONS),
        "prohibited_actions_performed": [],
        "failure_reasons": failure_reasons,
        "stopped_at": stopped_at,
        "created_at_utc": utc_now(),
    }
    plan = {
        "schema_version": "factory-improvement-execution-plan.v2",
        "status": result["status"],
        "execution_mode": result["execution_mode"],
        "plan_only": result["plan_only"],
        "improvement_requirements_path": result["improvement_requirements_path"],
        "improvement_sha256": result["improvement_sha256"],
        "factory_head": result["factory_head"],
        "factory_branch": result["factory_branch"],
        "approved_improvement_ids": result["approved_improvement_ids"],
        "before_after_delta": result["before_after_delta"],
        "workflow_evidence_markers": result["workflow_evidence_markers"],
        "prohibited_actions": result["prohibited_actions"],
        "stopped_at": result["stopped_at"],
        "created_at_utc": result["created_at_utc"],
    }
    write_json(output_root / "FACTORY_IMPROVEMENT_VALIDATION_REPORT.json", {"schema_version": "factory-improvement-validation-report.v2", "validation_reports": validation_reports})
    write_json(output_root / "FACTORY_IMPROVEMENT_CAPABILITY_DELTA.json", delta)
    write_json(output_root / "FACTORY_IMPROVEMENT_PROTECTED_ACTION_AUDIT.json", protected_action_audit)
    write_json(output_root / "FACTORY_IMPROVEMENT_WORKFLOW_RESULT.json", result)
    write_json(output_root / "FACTORY_IMPROVEMENT_EXECUTION_PLAN.json", plan)
    write_markdown(
        output_root / "FACTORY_IMPROVEMENT_EXECUTION_PLAN.md",
        render_execution_plan_markdown(plan),
    )
    return result
