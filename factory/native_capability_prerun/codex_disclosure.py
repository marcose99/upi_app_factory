from __future__ import annotations

from factory.evidence_portability import portable_json_dumps

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class CodexDisclosureError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexTaskDisclosure:
    task_id: str
    order: int
    objective: str
    role: str
    prompt: str
    output_schema: Mapping[str, Any]
    command: Sequence[str]
    sandbox: str
    mutability_boundary: str
    model: str
    reasoning_effort: str
    approval_policy: str
    working_directory: Path
    timeout_seconds: int
    inputs: Sequence[Mapping[str, Any]]
    evidence_paths: Sequence[str]
    protected_actions: Sequence[str]
    prohibited_actions: Sequence[str]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redacted_command(command: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    for item in command:
        if any(secret in item.lower() for secret in ("token=", "api_key=", "password=", "secret=")):
            redacted.append("[REDACTED_SECRET_ARGUMENT]")
        else:
            redacted.append(item)
    return redacted


def resolve_authenticated_model(
    *,
    catalogue: Mapping[str, Any],
    requested_model: str,
    requested_reasoning_effort: str,
) -> dict[str, Any]:
    """Resolve a requested model from an already authenticated zero-generation catalogue."""
    models = catalogue.get("models")
    if not isinstance(models, list) or not models:
        raise CodexDisclosureError("authenticated model catalogue is empty or malformed")
    visible: dict[str, Mapping[str, Any]] = {}
    for item in models:
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            visible[str(item["id"])] = item
    default_model = catalogue.get("default_model")
    model = str(default_model) if requested_model == "auto" and isinstance(default_model, str) else requested_model
    if model not in visible:
        raise CodexDisclosureError(f"requested model is unavailable to the authenticated account: {model}")
    efforts = visible[model].get("reasoning_efforts")
    if isinstance(efforts, list) and efforts and requested_reasoning_effort not in efforts:
        raise CodexDisclosureError("requested reasoning effort is unavailable for the resolved model")
    return {
        "requested_model": requested_model,
        "resolved_model": model,
        "catalogue_sha256": sha256_text(portable_json_dumps(catalogue, sort_keys=True)),
        "reasoning_effort": requested_reasoning_effort,
    }


def lifecycle_and_token_usage_from_jsonl_lines(lines: Sequence[str]) -> dict[str, Any]:
    counts = {
        "process_attempts": 0,
        "thread_started": 0,
        "turn_started": 0,
        "turn_completed": 0,
        "turn_failed": 0,
        "error_events": 0,
    }
    usage: dict[str, int | str] = {
        "input_tokens": "UNKNOWN",
        "cached_input_tokens": "UNKNOWN",
        "output_tokens": "UNKNOWN",
        "reasoning_output_tokens": "UNKNOWN",
    }
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        event_type = str(event.get("type", event.get("event", "")))
        if event_type == "process.attempted":
            counts["process_attempts"] += 1
        elif event_type == "thread.started":
            counts["thread_started"] += 1
        elif event_type == "turn.started":
            counts["turn_started"] += 1
        elif event_type == "turn.completed":
            counts["turn_completed"] += 1
            raw_usage = event.get("usage", {})
            if isinstance(raw_usage, Mapping):
                usage = {
                    "input_tokens": int(raw_usage.get("input_tokens", 0)),
                    "cached_input_tokens": int(raw_usage.get("cached_input_tokens", 0)),
                    "output_tokens": int(raw_usage.get("output_tokens", 0)),
                    "reasoning_output_tokens": int(raw_usage.get("reasoning_output_tokens", 0)),
                }
        elif event_type == "turn.failed":
            counts["turn_failed"] += 1
        elif "error" in event_type:
            counts["error_events"] += 1
    charged_usage = (
        "OBSERVED_TURN_COMPLETED_USAGE"
        if counts["turn_completed"]
        else "UNKNOWN_NO_COMPLETED_TURN_USAGE_EVENT"
        if counts["turn_started"] or counts["turn_failed"]
        else "NO_TURN_STARTED"
    )
    return {"lifecycle_counts": counts, "token_usage": usage, "charged_usage": charged_usage}


def global_configuration_summary(*, evidence_path: Path, stages: Sequence[str]) -> dict[str, Any]:
    summary = {
        "section": "GLOBAL_CODEX_CONFIGURATION_SUMMARY",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "codex_binary_resolution": "deferred_until_task_summary",
        "requested_model": "explicit_required",
        "authenticated_model_catalog_resolution": "required_before_codex_task",
        "reasoning_effort": "low_for_machine_consumed_stages",
        "approval_policy": "never_for_this_governed_local_stage",
        "sandbox": "workspace-write",
        "user_config_profile_behavior": "non_secret_summary_only",
        "session_persistence": "disabled_unless_explicitly_authorized",
        "structured_output": "strict_json_schema",
        "working_directory_policy": "isolated_feature_worktree",
        "web_search_network_mcp_connectors": "disabled",
        "authentication_source": "codex_cli_authenticated_account_without_secret_material",
        "limits": {"timeout_seconds": 0, "repair_cycles": 0, "repeated_failure_limit": 0},
        "instruction_sources_precedence": ["system", "developer", "AGENTS.md", "user"],
        "environment_inheritance_policy": "minimal_redacted",
        "command_line_overrides": [],
        "protected_actions": ["governance controls", "mock-only boundaries", "test thresholds"],
        "prohibited_actions": ["merge", "push", "tag", "release", "deployment", "live provider calls"],
        "stages": list(stages),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(portable_json_dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def task_configuration_summary(task: CodexTaskDisclosure, *, evidence_path: Path) -> dict[str, Any]:
    schema_text = portable_json_dumps(task.output_schema, indent=2, sort_keys=True)
    command = redacted_command(task.command)
    summary = {
        "section": "CODEX_TASK_CONFIGURATION_SUMMARY",
        "task_id": task.task_id,
        "execution_order": task.order,
        "objective": task.objective,
        "role": task.role,
        "expected_result": "strict schema-constrained JSON",
        "mutability_boundary": task.mutability_boundary,
        "prompt_begin_marker": "BEGIN_VERBATIM_CODEX_PROMPT",
        "prompt": task.prompt,
        "prompt_end_marker": "END_VERBATIM_CODEX_PROMPT",
        "output_schema_begin_marker": "BEGIN_VERBATIM_OUTPUT_JSON_SCHEMA",
        "output_schema": task.output_schema,
        "output_schema_end_marker": "END_VERBATIM_OUTPUT_JSON_SCHEMA",
        "prompt_identity": {
            "sha256": sha256_text(task.prompt),
            "size_bytes": len(task.prompt.encode("utf-8")),
            "line_count": len(task.prompt.splitlines()) or 1,
        },
        "schema_identity": {
            "sha256": sha256_text(schema_text),
            "size_bytes": len(schema_text.encode("utf-8")),
            "line_count": len(schema_text.splitlines()) or 1,
        },
        "codex_binary": {"requested": "codex", "resolved": "not_started_in_plan_only"},
        "model": task.model,
        "reasoning_effort": task.reasoning_effort,
        "approval_policy": task.approval_policy,
        "sandbox": task.sandbox,
        "config_profile_behavior": "isolated_non_secret",
        "session_persistence": "disabled",
        "web_network_policy": "disabled_except_authenticated_codex_transport",
        "mcp_connector_policy": "disabled",
        "skill_subagent_policy": "disabled",
        "command_redaction_policy": "redact token/api_key/password/secret argument material",
        "redacted_command": command,
        "working_directory": str(task.working_directory),
        "repository_state": "captured_by_invocation_evidence",
        "inputs": list(task.inputs),
        "runtime_paths": list(task.evidence_paths),
        "timeout_seconds": task.timeout_seconds,
        "environment_overrides": {},
        "authentication_source": "authenticated_codex_cli_without_secret_values",
        "secret_variable_presence": "names_only_when_present",
        "protected_actions": list(task.protected_actions),
        "prohibited_actions": list(task.prohibited_actions),
        "CODEX_TASK_CONFIGURATION_SUMMARY_COMPLETE": True,
    }
    if not summary["prompt"] or not summary["output_schema"]:
        raise CodexDisclosureError("task summary must include verbatim prompt and schema")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(portable_json_dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def compact_consolidated_log(stage_records: Sequence[Mapping[str, Any]], *, evidence_path: Path) -> dict[str, Any]:
    forbidden_keys = {"prompt", "output_schema", "raw_jsonl", "reasoning", "test_output"}
    forbidden_markers = ("BEGIN_VERBATIM", "END_VERBATIM", "verbatim prompt", "test output")

    def _contains_forbidden_payload(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if str(key) in forbidden_keys or _contains_forbidden_payload(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(_contains_forbidden_payload(item) for item in value)
        if isinstance(value, str):
            return any(marker in value for marker in forbidden_markers)
        return False

    compact_records = []
    for record in stage_records:
        if _contains_forbidden_payload(record):
            raise CodexDisclosureError("consolidated log attempted to retain excluded payload")
        compact_records.append(dict(record))
    payload = {"schema_version": "compact-codex-consolidated-log.v1", "records": compact_records}
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(portable_json_dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
