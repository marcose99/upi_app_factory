from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

import pytest

from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.executor import CapabilityExecutor
from tools.factory_control_plane.lifecycle import LifecycleState
from tools.factory_control_plane.manifest import Activity
from tools.factory_control_plane.policy import StandingPolicy

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_control_plane_authority_policy.py"
PHASE63 = ROOT / "scripts" / "validate_phase63_repository_governance.py"
SCHEMA = ROOT / "config" / "control_plane" / "protected_action_approval.schema.json"

EXPECTED_APPROVAL_FIELDS = {
    "action",
    "scope",
    "actor",
    "actor_type",
    "revision",
    "decision_id",
    "issued_at",
    "expires_at",
}
MACHINE_ACTORS = (
    "human:agent-controller",
    "human:agent01",
    "human:codexworker",
    "human:serviceaccount",
    "human:automation2",
    "human:buildbot",
    "human:controller99",
)
SENSITIVE_ENV = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GIT_ASKPASS",
    "SSH_AUTH_SOCK",
    "AWS_ACCESS_KEY_ID",
    "OPENAI_API_KEY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("authority_policy_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "default": "deny",
        "automatic_actions": ["inspect", "run_tests"],
        "human_required_actions": [
            "commit_candidate",
            "push_campaign_branch",
            "open_pull_request",
            "merge_pull_request",
        ],
        "prohibited_actions": ["force_push_main"],
    }


def _authority() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "decision_id": "HD-P0-01",
        "mode": "MANUAL_PROTECTED_ACTIONS",
        "authority_precedence": [
            "prohibited_actions",
            "human_required_actions",
            "automatic_actions",
            "default_deny",
        ],
        "conflict_resolution": "DENY",
        "default_resolution": "DENY",
        "protected_actions": [
            "commit_candidate",
            "create_campaign_branch",
            "push_campaign_branch",
            "open_pull_request",
            "merge_pull_request",
            "create_tag",
            "public_release",
            "production_deployment",
            "change_remote",
            "change_host_protection",
            "repository_settings_change",
            "real_payment_rail_access",
            "real_customer_data_access",
            "policy_exception",
            "destructive_migration",
            "certification_claim",
        ],
        "agent_delegation": {
            "allowed": False,
            "protected_actions_authorizable": [],
        },
    }


def _valid_approval() -> dict[str, object]:
    return {
        "action": "commit_candidate",
        "scope": "candidate:abc",
        "actor": "human:alice.reviewer",
        "actor_type": "HUMAN",
        "revision": "abc",
        "decision_id": "HD-P0-01",
        "issued_at": "2026-08-14T10:00:00+00:00",
        "expires_at": "2026-08-14T11:00:00+00:00",
    }


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


@contextmanager
def _mutated_schema(mutator: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    original = SCHEMA.read_bytes()
    payload = json.loads(original.decode("utf-8"))
    assert isinstance(payload, dict)
    mutator(payload)
    SCHEMA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        SCHEMA.write_bytes(original)


def _assert_schema_mutation_rejected(mutator: Callable[[dict[str, Any]], None]) -> None:
    module = _load()
    with _mutated_schema(mutator):
        assert module.validate_repository(ROOT)
        authority_cli = subprocess.run(
            [sys.executable, str(VALIDATOR), "--repo", str(ROOT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert authority_cli.returncode != 0, authority_cli.stdout
        phase63 = _run(PHASE63)
        assert phase63.returncode != 0, phase63.stdout


def _weaken(payload: dict[str, Any], case: str) -> None:
    properties = payload["properties"]
    assert isinstance(properties, dict)
    if case == "required_missing":
        payload["required"] = sorted(EXPECTED_APPROVAL_FIELDS - {"expires_at"})
    elif case == "additional_properties":
        payload["additionalProperties"] = True
    elif case == "unexpected_property":
        properties["unexpected"] = {"type": "string"}
    elif case == "actor_pattern":
        properties["actor"].pop("pattern", None)
    elif case == "actor_type_const":
        properties["actor_type"].pop("const", None)
    elif case == "decision_id_const":
        properties["decision_id"].pop("const", None)
    elif case == "issued_format":
        properties["issued_at"].pop("format", None)
    elif case == "expires_format":
        properties["expires_at"].pop("format", None)
    elif case == "identity_source":
        payload["x-upi-app-factory"]["actor_identity_source"] = "SELF_ASSERTED"
    elif case == "self_asserted":
        payload["x-upi-app-factory"]["self_asserted_actor_identity"] = True
    else:
        raise AssertionError(case)


def _schema_mutator(case: str) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        _weaken(payload, case)

    return mutate


class _ApprovalValidator(Protocol):
    def validate_human_approval_record(
        self,
        record: dict[str, object],
        *,
        action: str,
        scope: str,
        revision: str,
        now_utc: str,
        trusted_human_actors: frozenset[str] | None,
    ) -> list[str]: ...


def _approval_errors(
    module: _ApprovalValidator,
    record: dict[str, object],
    *,
    trusted_human_actors: frozenset[str] | None,
) -> list[str]:
    return module.validate_human_approval_record(
        record,
        action="commit_candidate",
        scope="candidate:abc",
        revision="abc",
        now_utc="2026-08-14T10:30:00Z",
        trusted_human_actors=trusted_human_actors,
    )


def _activity(
    argv: tuple[str, ...],
    *,
    action: str = "execute_engineering",
    kind: str = "execution",
    environment_allowlist: tuple[str, ...] = (),
    allowed_write_paths: tuple[str, ...] = (),
) -> Activity:
    return Activity(
        id="frozen",
        action=action,
        kind=kind,  # type: ignore[arg-type]
        risk="LOW",
        argv=argv,
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=5,
        cwd=".",
        environment_allowlist=environment_allowlist,
        allowed_write_paths=allowed_write_paths,
        digest="frozen",
    )


def test_repository_contract_and_cli_pass() -> None:
    module = _load()
    assert module.validate_repository(ROOT) == []
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--repo", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    phase63 = _run(PHASE63)
    assert phase63.returncode == 0, phase63.stdout


def test_automatic_human_conflict_and_default_resolution() -> None:
    module = _load()
    policy = _policy()
    authority = _authority()
    assert module.resolve_agent_action("inspect", policy, authority) == "ALLOW_AUTOMATIC"
    assert module.resolve_agent_action("commit_candidate", policy, authority) == "HUMAN_REQUIRED"
    assert module.resolve_agent_action("unknown_action", policy, authority) == "DENY"
    policy["automatic_actions"] = [*policy["automatic_actions"], "commit_candidate"]
    assert module.resolve_agent_action("commit_candidate", policy, authority) == "DENY"


def test_approval_schema_security_contract_is_frozen_through_phase63() -> None:
    for case in (
        "required_missing",
        "additional_properties",
        "unexpected_property",
        "actor_pattern",
        "actor_type_const",
        "decision_id_const",
        "issued_format",
        "expires_format",
        "identity_source",
        "self_asserted",
    ):
        _assert_schema_mutation_rejected(_schema_mutator(case))


def test_schema_rejects_machine_identity_fragments() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    actor = schema["properties"]["actor"]
    pattern = actor["pattern"]
    compiled = re.compile(pattern)
    assert compiled.search("human:alice.reviewer") is not None
    for identity in MACHINE_ACTORS:
        assert compiled.search(identity) is None, identity
    metadata = schema["x-upi-app-factory"]
    assert metadata["actor_identity_source"] == "TRUSTED_HUMAN_REGISTRY"
    assert metadata["self_asserted_actor_identity"] is False


def test_human_approval_requires_trusted_human_registry_and_strict_time() -> None:
    module = _load()
    valid = _valid_approval()
    assert _approval_errors(module, valid, trusted_human_actors=None)
    assert _approval_errors(
        module,
        valid,
        trusted_human_actors=frozenset({"human:alice.reviewer"}),
    ) == []

    for identity in MACHINE_ACTORS:
        record = {**valid, "actor": identity}
        assert _approval_errors(
            module,
            record,
            trusted_human_actors=frozenset({identity}),
        )

    mutations: list[dict[str, object]] = [
        {**valid, "scope": "candidate:WRONG"},
        {**valid, "revision": "WRONG"},
        {**valid, "action": "merge_pull_request"},
        {**valid, "decision_id": "HD-P0-WRONG"},
        {**valid, "actor_type": "AGENT"},
        {**valid, "issued_at": "2026-08-14 10:00:00+00:00"},
        {**valid, "issued_at": "2026-08-14T10:00+00:00"},
        {**valid, "issued_at": "2026-08-14T10:00:00"},
        {**valid, "issued_at": "2026-08-14T10:00:00+0000"},
        {**valid, "issued_at": "2026-08-14T10:31:00+00:00"},
        {**valid, "expires_at": "2026-08-14T09:59:59+00:00"},
        {**valid, "expires_at": "2026-08-14T10:29:59+00:00"},
        {**valid, "unexpected": "field"},
    ]
    trusted = frozenset({"human:alice.reviewer"})
    for record in mutations:
        assert _approval_errors(module, record, trusted_human_actors=trusted)


@pytest.mark.parametrize(
    "argv",
    [
        ("git", "commit", "-m", "x"),
        ("/usr/bin/git", "push", "origin", "HEAD"),
        ("git", "tag", "v-bad"),
        ("git", "branch", "bad"),
        ("git", "remote", "set-url", "origin", "https://example.invalid/x"),
        (
            "python3",
            "-c",
            "import subprocess; subprocess.run(['git','commit','-m','x'])",
        ),
        (
            "python3",
            "-c",
            "__import__('subprocess').run(['/usr/bin/git','push','origin','HEAD'])",
        ),
        (
            "python3",
            "-c",
            "import os; os.system('git tag v-bad')",
        ),
        (
            "python3",
            "-c",
            "import socket; socket.socket()",
        ),
    ],
)
def test_automatic_executor_rejects_protected_and_network_effects(
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    executor = CapabilityExecutor(tmp_path)
    with pytest.raises(ControlPlaneError):
        executor.run(_activity(argv))


@pytest.mark.parametrize(
    ("action", "kind"),
    [
        ("execute_engineering", "execution"),
        ("verify_evidence", "verification"),
        ("run_tests", "verification"),
    ],
)
def test_every_automatic_activity_alias_rejects_protected_git_effect(
    tmp_path: Path,
    action: str,
    kind: str,
) -> None:
    executor = CapabilityExecutor(tmp_path)
    with pytest.raises(ControlPlaneError):
        executor.run(
            _activity(
                ("git", "commit", "-m", "x"),
                action=action,
                kind=kind,
            )
        )


def test_executor_rejects_out_of_scope_local_write_before_effect(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    executor = CapabilityExecutor(tmp_path)
    with pytest.raises(ControlPlaneError):
        executor.run(
            _activity(
                (
                    "python3",
                    "-c",
                    "from pathlib import Path; Path('outside.txt').write_text('escape')",
                ),
                allowed_write_paths=("allowed",),
            )
        )
    assert not outside.exists()


def test_automatic_executor_rejects_script_level_protected_effect(tmp_path: Path) -> None:
    script = tmp_path / "malicious.py"
    script.write_text(
        "import subprocess\nsubprocess.run(['/usr/bin/git','commit','-m','x'])\n",
        encoding="utf-8",
    )
    executor = CapabilityExecutor(tmp_path)
    with pytest.raises(ControlPlaneError):
        executor.run(_activity(("python3", "malicious.py")))


@pytest.mark.parametrize("env_name", SENSITIVE_ENV)
def test_automatic_executor_rejects_sensitive_environment_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
) -> None:
    monkeypatch.setenv(env_name, "secret-or-capability")
    executor = CapabilityExecutor(tmp_path)
    with pytest.raises(ControlPlaneError):
        executor.run(
            _activity(
                ("python3", "-c", "print('x')"),
                environment_allowlist=(env_name,),
            )
        )


def test_production_standing_policy_conflicts_deny(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "default": "deny",
        "max_automatic_risk": "MODERATE",
        "automatic_actions": ["execute_engineering"],
        "human_required_actions": ["execute_engineering"],
        "prohibited_actions": [],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        policy = StandingPolicy(path)
    except ControlPlaneError:
        return
    assert policy.evaluate("execute_engineering", "LOW").outcome == "deny"


def test_engine_conflicting_policy_cannot_execute_activity(tmp_path: Path) -> None:
    policy_path = tmp_path / "standing_policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default": "deny",
                "max_automatic_risk": "MODERATE",
                "automatic_actions": ["execute_engineering"],
                "human_required_actions": ["execute_engineering"],
                "prohibited_actions": [],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "campaign.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "campaign_id": "frozen_conflict",
                "metadata": {},
                "baseline": "frozen-baseline",
                "objective": "prove production conflict denial",
                "scope": {"allowed_write_paths": ["runtime"]},
                "budgets": {"engineering_repairs": 0},
                "approvals": {},
                "validation_controls": {
                    "trusted_prerequisites": [],
                    "deterministic_runtime_noise": [],
                },
                "activities": [
                    {
                        "id": "must_not_execute",
                        "action": "execute_engineering",
                        "kind": "execution",
                        "risk": "LOW",
                        "argv": [
                            "python3",
                            "-c",
                            "from pathlib import Path; Path('runtime').mkdir(exist_ok=True); Path('runtime/escape.txt').write_text('bad')",
                        ],
                        "dependencies": [],
                        "target_state": "ENGINEERING",
                        "timeout_seconds": 5,
                        "cwd": ".",
                        "environment_allowlist": [],
                        "allowed_write_paths": ["runtime"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    try:
        engine = ControlPlaneEngine(tmp_path, tmp_path / "state", policy_path)
    except ControlPlaneError:
        return
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert not (tmp_path / "runtime/escape.txt").exists()
    finally:
        engine.close()


def test_valid_human_record_never_delegates_agent_authority() -> None:
    module = _load()
    assert module.resolve_agent_action("commit_candidate", _policy(), _authority()) == "HUMAN_REQUIRED"

@contextmanager
def _mutated_capability_registry(
    mutator: Callable[[dict[str, Any]], None],
) -> Iterator[None]:
    registry = ROOT / "config" / "control_plane" / "automatic_capabilities.json"
    original = registry.read_bytes()
    payload = json.loads(original.decode("utf-8"))
    assert isinstance(payload, dict)
    mutator(payload)
    registry.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        yield
    finally:
        registry.write_bytes(original)


def _assert_capability_registry_mutation_rejected(
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    module = _load()
    with _mutated_capability_registry(mutator):
        assert module.validate_repository(ROOT)
        authority_cli = subprocess.run(
            [sys.executable, str(VALIDATOR), "--repo", str(ROOT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert authority_cli.returncode != 0, authority_cli.stdout
        phase63 = _run(PHASE63)
        assert phase63.returncode != 0, phase63.stdout


def _weaken_capability_registry(payload: dict[str, Any], case: str) -> None:
    capabilities = payload.get("capabilities")
    assert isinstance(capabilities, list)
    python_capability = next(
        item
        for item in capabilities
        if isinstance(item, dict) and item.get("kind") == "python_script"
    )
    if case == "environment_inheritance":
        python_capability["environment"] = ["PATH"]
    elif case == "network_enabled":
        python_capability["network"] = True
    elif case == "executable_substitution":
        python_capability["executable"] = "/tmp/attacker/python3"
    elif case == "protected_write_root":
        python_capability["write_roots"] = [".git"]
        payload["disposable_roots"] = [".git"]
    else:
        raise AssertionError(case)


def _capability_registry_mutator(
    case: str,
) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        _weaken_capability_registry(payload, case)

    return mutate


def test_runtime_noise_rejects_protected_and_out_of_scope_targets() -> None:
    from tools.factory_control_plane.capability_guard import CapabilityGuard

    guard = CapabilityGuard(ROOT)
    with pytest.raises(ControlPlaneError):
        guard.validate_runtime_noise(".git", (".git",))
    with pytest.raises(ControlPlaneError):
        guard.validate_runtime_noise(
            "var/control_plane_self_test",
            ("factory_governance/phase68_70/recipient_replay_output",),
        )


@pytest.mark.parametrize(
    "argv",
    [
        ("/tmp/attacker/python3", "-c", "print('x')"),
        ("./python3", "-c", "print('x')"),
        (
            "python3",
            "-c",
            "getattr(__builtins__, '__import__')('subprocess').run(['git','commit','-m','x'])",
        ),
        (
            "python3",
            "-c",
            "from pathlib import Path; getattr(Path('outside.txt'),'write_text')('escape')",
        ),
    ],
)
def test_unregistered_or_dynamic_execution_is_rejected_before_effect(
    argv: tuple[str, ...],
    tmp_path: Path,
) -> None:
    executor = CapabilityExecutor(tmp_path)
    outside = tmp_path / "outside.txt"
    with pytest.raises(ControlPlaneError):
        executor.run(_activity(argv))
    assert not outside.exists()


def test_capability_registry_identity_environment_and_network_are_frozen() -> None:
    for case in (
        "environment_inheritance",
        "network_enabled",
        "executable_substitution",
        "protected_write_root",
    ):
        _assert_capability_registry_mutation_rejected(
            _capability_registry_mutator(case)
        )
PROTECTED_HYDRATION_ROOTS = (
    ".git",
    ".github",
    "config",
    "docs",
    "factory",
    "scripts",
    "src",
    "tests",
    "tools",
)


def _hydration_manifest_payload(scope_root: str, prerequisite_path: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "campaign_id": "frozen_hydration_boundary",
        "metadata": {},
        "baseline": "frozen-baseline",
        "objective": "prove hydrated prerequisites cannot target protected repository content",
        "scope": {"allowed_write_paths": [scope_root]},
        "budgets": {"engineering_repairs": 0},
        "approvals": {},
        "validation_controls": {
            "trusted_prerequisites": [
                {
                    "id": "attacker_selected_hydration",
                    "kind": "directory",
                    "path": prerequisite_path,
                    "hydrate": True,
                }
            ],
            "deterministic_runtime_noise": [],
        },
        "activities": [
            {
                "id": "read_only_checkpoint",
                "action": "verify_evidence",
                "kind": "verification",
                "risk": "LOW",
                "argv": ["capability:self_test_verify"],
                "dependencies": [],
                "target_state": "OFFLINE_VALIDATED",
                "timeout_seconds": 5,
                "cwd": ".",
                "environment_allowlist": [],
                "allowed_write_paths": [],
            }
        ],
    }


@pytest.mark.parametrize("protected_root", PROTECTED_HYDRATION_ROOTS)
def test_hydrated_prerequisite_rejects_protected_repository_roots_before_effect(
    tmp_path: Path,
    protected_root: str,
) -> None:
    from tools.factory_control_plane.manifest import load_manifest

    root = tmp_path / protected_root
    root.mkdir(parents=True, exist_ok=True)
    target = f"{protected_root}/frozen-hydration"
    manifest_path = tmp_path / "campaign.json"
    manifest_path.write_text(
        json.dumps(_hydration_manifest_payload(protected_root, target)),
        encoding="utf-8",
    )

    with pytest.raises(ControlPlaneError):
        load_manifest(manifest_path, tmp_path)

    assert not (tmp_path / target).exists()


def test_hydrated_prerequisite_rejects_symlink_indirection_to_protected_root(
    tmp_path: Path,
) -> None:
    from tools.factory_control_plane.manifest import load_manifest

    protected = tmp_path / ".git" / "protected"
    protected.mkdir(parents=True)
    runtime = tmp_path / "runtime"
    runtime.symlink_to(protected, target_is_directory=True)
    manifest_path = tmp_path / "campaign.json"
    manifest_path.write_text(
        json.dumps(_hydration_manifest_payload("runtime", "runtime/frozen-hydration")),
        encoding="utf-8",
    )

    with pytest.raises(ControlPlaneError):
        load_manifest(manifest_path, tmp_path)

    assert not (protected / "frozen-hydration").exists()


def _write_frozen_capability_registry(root: Path, write_root: str) -> None:
    registry = root / "config" / "control_plane" / "automatic_capabilities.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": [write_root],
                "capabilities": [
                    {
                        "id": "frozen_write",
                        "request_argv": ["capability:frozen_write"],
                        "kind": "internal",
                        "executable": None,
                        "script": None,
                        "script_sha256": None,
                        "arguments": [],
                        "effects": ["write"],
                        "write_roots": [write_root],
                        "environment": [],
                        "network": False,
                        "replace_write_root": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "protected_root",
    (".git", ".github", "config", "docs", "factory", "scripts", "src", "tests", "tools"),
)
def test_capability_registry_rejects_direct_protected_write_roots(
    tmp_path: Path,
    protected_root: str,
) -> None:
    from tools.factory_control_plane.capability_guard import CapabilityGuard

    (tmp_path / protected_root).mkdir(parents=True, exist_ok=True)
    _write_frozen_capability_registry(tmp_path, protected_root)

    with pytest.raises(ControlPlaneError):
        CapabilityGuard(tmp_path)


def test_capability_registry_rejects_preexisting_symlink_write_root(
    tmp_path: Path,
) -> None:
    from tools.factory_control_plane.capability_guard import CapabilityGuard

    protected = tmp_path / ".git" / "protected"
    protected.mkdir(parents=True)
    runtime = tmp_path / "runtime"
    runtime.symlink_to(protected, target_is_directory=True)
    _write_frozen_capability_registry(tmp_path, "runtime")

    with pytest.raises(ControlPlaneError):
        CapabilityGuard(tmp_path)
