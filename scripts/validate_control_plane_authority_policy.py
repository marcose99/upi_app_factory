from __future__ import annotations

import argparse
import ast
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import AbstractSet, Any, cast


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


def resolve_agent_action(action: str, policy: dict[str, Any], authority: dict[str, Any]) -> str:
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
    if (
        authority.get("conflict_resolution") != "DENY"
        or authority.get("default_resolution") != "DENY"
    ):
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
        from tools.factory_control_plane.executor import (
            _NETWORK_DENY_SYSCALLS,
            _github_ci_share_host_network_namespace,
            build_application_argv,
            build_isolation_argv,
        )
        from tools.factory_control_plane.host_runtime import resolve_python_runtime
        from tools.factory_control_plane.common import ControlPlaneError
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
            executable=resolve_python_runtime(),
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
            str(resolve_python_runtime()),
            "/run/upi_app_factory_project/scripts/contract.py",
            "--contract-argument",
        ]:
            errors.append("executor command planner breaks executable/script argv assembly")
        if build_isolation_argv(False, 17) != ("--unshare-all", "--share-net", "--seccomp", "17"):
            errors.append("production isolation argv is not canonical")
        if build_isolation_argv(True, 17) != ("--unshare-all", "--share-net", "--seccomp", "17"):
            errors.append("GitHub CI fallback isolation argv is not canonical")
        if _github_ci_share_host_network_namespace({}) is not False:
            errors.append("empty environment enables share-net")
        if (
            _github_ci_share_host_network_namespace(
                {
                    "UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1",
                    "GITHUB_ACTIONS": "true",
                    "CI": "true",
                }
            )
            is not True
        ):
            errors.append("complete GitHub CI opt-in does not enable share-net")
        for environment in (
            {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "0"},
            {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1"},
            {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1", "GITHUB_ACTIONS": "true"},
            {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1", "CI": "true"},
        ):
            try:
                _github_ci_share_host_network_namespace(environment)
            except ControlPlaneError:
                pass
            else:
                errors.append("partial/invalid GitHub CI share-net opt-in accepted")
                break
        if tuple(_NETWORK_DENY_SYSCALLS) != (
            "socket",
            "socketpair",
            "connect",
            "bind",
            "listen",
            "accept",
            "accept4",
            "io_uring_setup",
            "io_uring_enter",
            "io_uring_register",
            "bpf",
        ):
            errors.append("network seccomp denylist changed")
        errors.extend(
            _validate_executor_structure(repo / "tools/factory_control_plane/executor.py")
        )
        engine = (repo / "tools/factory_control_plane/engine.py").read_text(encoding="utf-8")
        if engine.find("_authorize_before_mutation(manifest)") > engine.find(
            "create_or_load_campaign"
        ):
            errors.append("engine mutation precedes capability and policy authorization")
    except Exception as exc:
        errors.append(f"automatic capability validation failed: {exc}")
    return errors


def _validate_executor_structure(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors = []
    cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CapabilityExecutor"),
        None,
    )
    if cls is None:
        return ["CapabilityExecutor class is absent"]
    run = next(
        (
            n
            for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_run"
        ),
        None,
    )
    if run is None:
        return ["executor command runner is absent"]
    parent = {child: node for node in ast.walk(run) for child in ast.iter_child_nodes(node)}

    def assigns(name: str) -> list[ast.Assign]:
        return [
            n
            for n in ast.walk(run)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        ]

    def require_direct(statement: ast.AST | None, name: str) -> None:
        if statement is not None and parent.get(statement) is not run:
            errors.append(
                f"executor security assignment {name} is not on the direct live _run path"
            )

    def callassign(name: str, fn: str, args: tuple[str, ...]) -> ast.Assign | None:
        a = assigns(name)
        if len(a) != 1:
            errors.append(f"executor must assign {name} exactly once")
            return None
        v = a[0].value
        if (
            not isinstance(v, ast.Call)
            or not isinstance(v.func, ast.Name)
            or v.func.id != fn
            or tuple(ast.unparse(x) for x in v.args) != args
            or v.keywords
        ):
            errors.append(f"executor {name} assignment is not canonical")
            return None
        return a[0]

    sec = callassign("seccomp_fd", "_network_seccomp_fd", ())
    share = callassign("share_network", "_github_ci_share_host_network_namespace", ())
    iso = callassign("isolation_argv", "build_isolation_argv", ("share_network", "seccomp_fd"))
    for statement, name in ((sec, "seccomp_fd"), (share, "share_network"), (iso, "isolation_argv")):
        require_direct(statement, name)
    ca = assigns("command")
    command = ca[0] if len(ca) == 1 else None
    require_direct(command, "command")
    if command is None or not isinstance(command.value, ast.List):
        errors.append("executor command construction is not canonical")
    elif (
        len(
            [
                x
                for x in command.value.elts
                if isinstance(x, ast.Starred)
                and isinstance(x.value, ast.Name)
                and x.value.id == "isolation_argv"
            ]
        )
        != 1
    ):
        errors.append("command does not consume isolation_argv exactly once")
    plan_nodes = [
        n
        for n in ast.walk(run)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "plan" for t in n.targets)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "ExecutionPlan"
    ]
    plans: list[ast.Call] = [cast(ast.Call, n.value) for n in plan_nodes]
    if len(plans) != 1:
        errors.append("executor must construct exactly one typed plan")
    else:
        fields = {x.arg: ast.unparse(x.value) for x in plans[0].keywords}
        expected = {
            "command": "tuple(command)",
            "application_argv": "tuple(application_argv)",
            "network_namespace": "False",
            "seccomp_fd": "seccomp_fd",
            "stdin": "subprocess.DEVNULL",
            "close_fds": "True",
        }
        for k, v in expected.items():
            if fields.get(k) != v:
                errors.append(f"typed plan field {k} is not canonical")
        pf = next((x.value for x in plans[0].keywords if x.arg == "pass_fds"), None)
        expected_pass_fds = (
            "(temporary_fd, project_fd, seccomp_fd, "
            "*(output_handle.fd for output_handle in output_handles), "
            "*((private_script_fd,) if private_script_fd >= 0 else ()))"
        )
        if pf is None or ast.unparse(pf) != expected_pass_fds:
            errors.append("typed plan pass_fds is not the canonical closed descriptor tuple")
    calls = [
        c
        for c in ast.walk(run)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id == "subprocess"
        and c.func.attr == "run"
    ]
    if len(calls) != 1:
        errors.append("executor must contain exactly one subprocess sink")
    else:
        c = calls[0]
        kw = {x.arg: ast.unparse(x.value) for x in c.keywords}
        exp = {
            "cwd": "plan.cwd",
            "env": "plan.environment",
            "timeout": "plan.timeout_seconds",
            "pass_fds": "plan.pass_fds",
            "stdin": "plan.stdin",
            "close_fds": "plan.close_fds",
            "capture_output": "True",
            "text": "True",
            "check": "False",
        }
        if not c.args or ast.unparse(c.args[0]) != "plan.command":
            errors.append("subprocess does not consume plan.command")
        for k, v in exp.items():
            if kw.get(k) != v:
                errors.append(f"subprocess field {k} is not canonical")
        if len(plan_nodes) == 1:
            sink_statement = parent.get(c)
            plan_parent = parent.get(plan_nodes[0])
            sink_parent = parent.get(sink_statement) if sink_statement is not None else None
            if (
                not isinstance(plan_parent, ast.Try)
                or plan_parent is not sink_parent
                or parent.get(plan_parent) is not run
            ):
                errors.append(
                    "typed plan and subprocess sink are not direct ordered statements in the same live _run try block"
                )
            elif (
                plan_nodes[0] not in plan_parent.body
                or sink_statement not in plan_parent.body
                or plan_parent.body.index(plan_nodes[0]) >= plan_parent.body.index(sink_statement)
            ):
                errors.append("subprocess sink can execute before typed plan capture")
    if sec is not None and share is not None and iso is not None and command is not None:
        order = [sec.lineno, share.lineno, iso.lineno, command.lineno]
        if order != sorted(order):
            errors.append("isolation construction order changed")

        security_assignments = {
            "seccomp_fd": sec,
            "share_network": share,
            "isolation_argv": iso,
        }
        for name, original in security_assignments.items():
            for node in ast.walk(run):
                if node is original:
                    continue
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                    targets = [node.target]
                else:
                    continue
                if node.lineno > original.lineno and any(
                    _targets_name(target, name) for target in targets
                ):
                    errors.append(f"security input {name} is rebound after canonical assignment")
                    break

    if sec is not None and share is not None and iso is not None:
        for name, original in {
            "seccomp_fd": sec,
            "share_network": share,
            "isolation_argv": iso,
        }.items():
            for node in ast.walk(run):
                if node is original or not hasattr(node, "lineno"):
                    continue
                if node.lineno > original.lineno and _node_binds_or_mutates_name(node, name):
                    errors.append(
                        f"security input {name} is rebound by a Python binding or mutation form"
                    )
                    break

    generic_plan_mutations = [
        node for node in ast.walk(run) if _node_binds_or_mutates_name(node, "plan")
    ]
    if (
        len(generic_plan_mutations) != 1
        or not plan_nodes
        or generic_plan_mutations[0] is not plan_nodes[0]
    ):
        errors.append(
            "typed plan must have one definition across all Python binding/mutation forms"
        )

    plan_mutations = []
    for node in ast.walk(run):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        else:
            continue
        if any(_targets_name(target, "plan") for target in targets):
            plan_mutations.append(node)
    if len(plan_mutations) != 1 or not plan_nodes or plan_mutations[0] is not plan_nodes[0]:
        errors.append("typed plan must have exactly one definition and no later rebinding")
    for node in ast.walk(run):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "command"
            and node.func.attr not in {"extend", "append"}
        ):
            errors.append(f"executor performs non-monotonic command mutation: {node.func.attr}")
        if isinstance(node, (ast.Delete, ast.AugAssign)) and any(
            isinstance(x, ast.Name) and x.id == "command" for x in ast.walk(node)
        ):
            errors.append("executor performs destructive command mutation")
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for n in (
        "build_isolation_argv",
        "_github_ci_share_host_network_namespace",
        "_network_seccomp_fd",
    ):
        if n not in funcs:
            errors.append(f"executor security helper absent: {n}")
    if "_network_seccomp_fd" in funcs and "_NETWORK_DENY_SYSCALLS" not in ast.unparse(
        funcs["_network_seccomp_fd"]
    ):
        errors.append("seccomp builder does not consume frozen denylist")
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


def _rooted_in_name(value: ast.AST | None, name: str) -> bool:
    if value is None:
        return False
    if isinstance(value, ast.Name):
        return value.id == name
    if isinstance(value, (ast.Attribute, ast.Subscript, ast.Starred)):
        return _rooted_in_name(value.value, name)
    return False


def _generic_targets_name(target: ast.AST, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Attribute, ast.Subscript, ast.Starred)):
        return _rooted_in_name(target.value, name)
    if isinstance(target, (ast.List, ast.Tuple)):
        return any(_generic_targets_name(item, name) for item in target.elts)
    return False


def _import_binds_name(alias: ast.alias, name: str) -> bool:
    bound = alias.asname or alias.name.split(".", 1)[0]
    return bound == name


def _node_binds_or_mutates_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Assign):
        return any(_generic_targets_name(target, name) for target in node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return _generic_targets_name(node.target, name)
    if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
        return _generic_targets_name(node.target, name)
    if isinstance(node, ast.withitem):
        return node.optional_vars is not None and _generic_targets_name(node.optional_vars, name)
    if isinstance(node, ast.ExceptHandler):
        return node.name == name
    if isinstance(node, ast.Delete):
        return any(_generic_targets_name(target, name) for target in node.targets)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any(_import_binds_name(alias, name) for alias in node.names)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)):
        return node.name == name
    if isinstance(node, ast.MatchMapping):
        return node.rest == name
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and _rooted_in_name(node.func.value, name):
            return True
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"setattr", "delattr"}
            and node.args
            and _rooted_in_name(node.args[0], name)
        ):
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "object"
            and node.func.attr in {"__setattr__", "__delattr__"}
            and node.args
            and _rooted_in_name(node.args[0], name)
        ):
            return True
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
