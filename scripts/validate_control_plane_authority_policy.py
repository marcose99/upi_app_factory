from __future__ import annotations

import argparse
import ast
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import AbstractSet, Any


APPROVAL_FIELDS = {
    "action",
    "scope",
    "actor",
    "actor_type",
    "revision",
    "decision_id",
    "issued_at",
    "expires_at",
}
ACTOR_PATTERN = (
    r"^human:(?!.*(?:agent|codex|serviceaccount|automation|buildbot|controller))"
    r"[a-z][a-z0-9._-]{2,63}$"
)
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
MACHINE_ACTOR_PATTERN = re.compile(
    r"(?:agent|codex|serviceaccount|automation|buildbot|controller)", re.IGNORECASE
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return {str(key): item for key, item in value.items()}


def resolve_agent_action(
    action: str, policy: dict[str, Any], authority: dict[str, Any]
) -> str:
    automatic = _members(policy, "automatic_actions")
    human = _members(policy, "human_required_actions")
    prohibited = _members(policy, "prohibited_actions")
    memberships = sum(action in group for group in (automatic, human, prohibited))
    if memberships > 1:
        return "DENY"
    if action in prohibited:
        return "DENY"
    if action in human:
        return "HUMAN_REQUIRED"
    protected = _string_set(authority.get("protected_actions"))
    if action in protected:
        return "DENY"
    if action in automatic:
        return "ALLOW_AUTOMATIC"
    return "DENY"


def validate_human_approval_record(
    record: dict[str, object],
    *,
    action: str,
    scope: str,
    revision: str,
    now_utc: str,
    trusted_human_actors: AbstractSet[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if set(record) != APPROVAL_FIELDS:
        errors.append("approval fields do not match the frozen contract")
    expected = {
        "action": action,
        "scope": scope,
        "revision": revision,
        "actor_type": "HUMAN",
        "decision_id": "HD-P0-01",
    }
    for key, value in expected.items():
        if record.get(key) != value:
            errors.append(f"approval {key} does not match")
    actor = record.get("actor")
    if not isinstance(actor, str) or re.fullmatch(ACTOR_PATTERN, actor) is None:
        errors.append("actor is not an eligible human identity")
    elif MACHINE_ACTOR_PATTERN.search(actor):
        errors.append("machine-role actor identity is prohibited")
    if trusted_human_actors is None:
        errors.append("trusted human registry was not supplied")
    elif not isinstance(actor, str) or actor not in trusted_human_actors:
        errors.append("actor is absent from the trusted human registry")

    issued = _timestamp(record.get("issued_at"), "issued_at", errors)
    expires = _timestamp(record.get("expires_at"), "expires_at", errors)
    now = _timestamp(now_utc, "now_utc", errors)
    if issued is not None and expires is not None and expires <= issued:
        errors.append("approval expiry must be after issuance")
    if issued is not None and now is not None and issued > now:
        errors.append("approval was issued in the future")
    if expires is not None and now is not None and expires < now:
        errors.append("approval has expired")
    return errors


def validate_repository(repo: Path) -> list[str]:
    errors: list[str] = []
    base = repo.resolve() / "config/control_plane"
    try:
        policy = _load(base / "standing_policy.json")
        authority = _load(base / "authority_precedence.json")
        schema = _load(base / "protected_action_approval.schema.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    automatic = _members(policy, "automatic_actions")
    human = _members(policy, "human_required_actions")
    prohibited = _members(policy, "prohibited_actions")
    overlap = (automatic & human) | (automatic & prohibited) | (human & prohibited)
    if overlap:
        errors.append(f"policy memberships overlap: {sorted(overlap)}")
    if policy.get("default") != "deny":
        errors.append("standing policy default must deny")
    if authority.get("decision_id") != "HD-P0-01":
        errors.append("authority decision is not HD-P0-01")
    if authority.get("mode") != "MANUAL_PROTECTED_ACTIONS":
        errors.append("authority mode is not MANUAL_PROTECTED_ACTIONS")
    if authority.get("conflict_resolution") != "DENY" or authority.get("default_resolution") != "DENY":
        errors.append("authority conflict and default resolutions must deny")
    delegation = authority.get("agent_delegation")
    if delegation != {"allowed": False, "protected_actions_authorizable": []}:
        errors.append("protected authority must not be delegated to agents")
    protected = _string_set(authority.get("protected_actions"))
    if automatic & protected:
        errors.append(f"protected actions are automatic: {sorted(automatic & protected)}")
    errors.extend(_validate_frozen_schema(schema))
    errors.extend(_validate_capability_registry(repo.resolve()))
    return errors


def _validate_capability_registry(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from tools.factory_control_plane.capability_guard import CapabilityGuard, ResolvedCapability
        from tools.factory_control_plane.executor import build_application_argv
        from tools.factory_control_plane.manifest import load_manifest

        guard = CapabilityGuard(repo)
        for relative in (
            "config/control_plane/campaigns/control_plane_self_test.json",
            "config/control_plane/campaigns/phase68_70_consolidated_capstone.json",
        ):
            manifest = load_manifest(repo / relative, repo)
            for activity in manifest.activities:
                guard.resolve(activity)
            scope = tuple(manifest.scope.get("allowed_write_paths", []))
            for item in manifest.validation_controls.deterministic_runtime_noise:
                guard.validate_runtime_noise(item.path, scope)
        contract = ResolvedCapability(
            capability_id="validator_contract",
            kind="python_script",
            executable=Path("/usr/bin/python3"),
            arguments=("--contract-argument",),
            write_roots=(),
            network=False,
            replace_write_root=False,
            script_fd=7,
            script_relative="scripts/contract.py",
        )
        planned = build_application_argv(
            contract,
            repo,
            Path("/run/upi_app_factory_project"),
            Path("/run/upi_app_factory_project/scripts/contract.py"),
        )
        if planned != [
            "/usr/bin/python3",
            "/run/upi_app_factory_project/scripts/contract.py",
            "--contract-argument",
        ]:
            errors.append("executor command planner breaks executable/script argv assembly")
        errors.extend(_validate_executor_structure(repo / "tools/factory_control_plane/executor.py"))
        engine = (repo / "tools/factory_control_plane/engine.py").read_text(encoding="utf-8")
        if engine.find("_authorize_before_mutation(manifest)") > engine.find("create_or_load_campaign"):
            errors.append("engine mutation precedes capability and policy authorization")
    except Exception as exc:
        errors.append(f"automatic capability validation failed: {exc}")
    return errors


def _validate_executor_structure(path: Path) -> list[str]:
    """Validate the one typed plan and the exact subprocess data flow."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    run_method = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_run"
        ),
        None,
    )
    if run_method is None:
        return ["executor command runner is absent"]
    calls = [node for node in ast.walk(run_method) if isinstance(node, ast.Call)]
    subprocess_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "subprocess"
        and call.func.attr == "run"
    ]
    errors: list[str] = []
    live_statements = _live_top_level_statements(run_method)
    plan_statements = [
        (index, node)
        for index, node in enumerate(live_statements)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "plan" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "ExecutionPlan"
    ]
    application_extensions = [
        (index, node)
        for index, node in enumerate(live_statements)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "command"
        and node.value.func.attr == "extend"
        and len(node.value.args) == 1
        and not node.value.keywords
        and isinstance(node.value.args[0], ast.Name)
        and node.value.args[0].id == "application_argv"
    ]
    if len(application_extensions) != 1:
        errors.append(
            "executor must extend the live command exactly once with the full application argv"
        )
    elif len(plan_statements) == 1:
        extension_index = application_extensions[0][0]
        plan_index = plan_statements[0][0]
        if extension_index >= plan_index:
            errors.append("application argv must feed the command before plan capture")
        elif any(
            isinstance(node, ast.Name) and node.id == "command"
            for statement in live_statements[extension_index + 1 : plan_index]
            for node in ast.walk(statement)
        ):
            errors.append("executor uses or mutates the command before plan capture")
        if any(
            _mutates_name(statement, "plan")
            for statement in live_statements[plan_index + 1 :]
        ):
            errors.append("executor mutates the execution plan after command capture")
    plans = [
        node.value for node in ast.walk(run_method)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "plan" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "ExecutionPlan"
    ]
    if len(plans) != 1:
        errors.append("executor must construct exactly one typed execution plan")
    else:
        fields = {item.arg: ast.unparse(item.value) for item in plans[0].keywords}
        expected = {
            "command": "tuple(command)",
            "application_argv": "tuple(application_argv)",
            "network_namespace": "True",
            "seccomp_fd": "seccomp_fd",
        }
        if any(fields.get(key) != value for key, value in expected.items()):
            errors.append("typed execution plan relationships are not canonical")
        if "--output-root" not in {n.value for n in ast.walk(run_method) if isinstance(n, ast.Constant)}:
            errors.append("typed execution plan does not bind the staged output root")
    if len(subprocess_calls) != 1:
        errors.append("executor must contain exactly one subprocess execution sink")
    else:
        call = subprocess_calls[0]
        keywords = {item.arg: ast.unparse(item.value) for item in call.keywords}
        if not call.args or ast.unparse(call.args[0]) != "plan.command":
            errors.append("subprocess does not consume the typed plan command")
        expected_keywords = {
            "cwd": "plan.cwd", "env": "plan.environment", "timeout": "plan.timeout_seconds",
            "pass_fds": "plan.pass_fds",
        }
        if any(keywords.get(key) != value for key, value in expected_keywords.items()):
            errors.append("subprocess does not consume the typed plan security fields")
    constants = {
        node.value for node in ast.walk(run_method) if isinstance(node, ast.Constant)
    }
    if not {"--ro-bind", "--unshare-all", "--seccomp"}.issubset(constants):
        errors.append("executor does not enforce minimal filesystem and network namespaces")
    source = ast.unparse(run_method)
    if '"--ro-bind", "/", "/"' in source or "'--ro-bind', '/', '/'" in source:
        errors.append("executor exposes the host root")
    return errors


def _live_top_level_statements(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    """Return the direct statement sequence up to an unconditional terminator."""
    statements: list[ast.stmt] = []
    for statement in function.body:
        statements.append(statement)
        if isinstance(statement, (ast.Return, ast.Raise)):
            break
    return statements


def _mutates_name(statement: ast.stmt, name: str) -> bool:
    """Return whether a live statement can rebind or mutate a captured value."""
    for node in ast.walk(statement):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets: list[ast.expr]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            if any(_targets_name(target, name) for target in targets):
                return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == name
        ):
            return True
    return False


def _targets_name(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Attribute, ast.Subscript)):
        return isinstance(target.value, ast.Name) and target.value.id == name
    if isinstance(target, (ast.List, ast.Tuple)):
        return any(_targets_name(item, name) for item in target.elts)
    return False


def _validate_frozen_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties")
    if not isinstance(properties, dict) or set(properties) != APPROVAL_FIELDS:
        return ["approval schema properties do not match the frozen contract"]
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        errors.append("approval schema must be a closed object")
    if set(schema.get("required", [])) != APPROVAL_FIELDS:
        errors.append("approval schema required fields are incomplete")
    expected_properties: dict[str, dict[str, object]] = {
        "action": {"minLength": 1, "type": "string"},
        "scope": {"minLength": 1, "type": "string"},
        "actor": {"pattern": ACTOR_PATTERN, "type": "string"},
        "actor_type": {"const": "HUMAN"},
        "revision": {"minLength": 1, "type": "string"},
        "decision_id": {"const": "HD-P0-01"},
        "issued_at": {"format": "date-time", "type": "string"},
        "expires_at": {"format": "date-time", "type": "string"},
    }
    if properties != expected_properties:
        errors.append("approval schema property constraints changed")
    metadata = schema.get("x-upi-app-factory")
    if metadata != {
        "actor_identity_source": "TRUSTED_HUMAN_REGISTRY",
        "authorization_effect": "HUMAN_ACTION_EVIDENCE_ONLY",
        "decision_id": "HD-P0-01",
        "delegation_to_agents": False,
        "self_asserted_actor_identity": False,
    }:
        errors.append("approval schema security metadata changed")
    return errors


def _timestamp(value: object, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or RFC3339_PATTERN.fullmatch(value) is None:
        errors.append(f"{label} is not strict RFC3339")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} is not a valid timestamp")
        return None


def _members(payload: dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    return _string_set(value) if isinstance(value, list) else set()


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_repository(args.repo)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2, sort_keys=True))
        return 1
    print(json.dumps({"status": "passed", "decision_id": "HD-P0-01"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
