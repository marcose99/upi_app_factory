from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane import executor as executor_module
from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.executor import ActivityResult, CapabilityExecutor
from tools.factory_control_plane.fs_guard import FilesystemGuard
from tools.factory_control_plane.failures import FailureClass, consumes_repair_budget
from tools.factory_control_plane.lifecycle import LifecycleState
from tools.factory_control_plane.manifest import Activity, load_manifest
from tools.factory_control_plane.state import StateStore


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "config/control_plane/campaigns/control_plane_self_test.json"
POLICY = ROOT / "config/control_plane/standing_policy.json"


class _ControlledGuard:
    def resolve(self, _activity: object) -> object:
        return object()

    def validate_runtime_noise(self, path: str, _scope: tuple[str, ...]) -> Path:
        return Path(path)


class _ControlledExecutor:
    """Test-only lifecycle fixture; it grants no production command capability."""

    def __init__(
        self, root: Path, baseline_code: int = 0, candidate_code: int = 0, run_code: int = 0
    ) -> None:
        self.guard = _ControlledGuard()
        self.filesystem = FilesystemGuard(root)
        self.baseline_code = baseline_code
        self.candidate_code = candidate_code
        self.run_code = run_code

    @staticmethod
    def _result(activity: object, code: int) -> ActivityResult:
        item = cast(Any, activity)
        return ActivityResult(item.id, item.action, item.kind, code, "out", "err", "", "", "start", "finish")

    def run(self, activity: object) -> ActivityResult:
        return self._result(activity, self.run_code)

    def close(self) -> None:
        self.filesystem.close()

    def observe(self, activity: object, subject: str, _reference: str) -> ActivityResult:
        code = self.baseline_code if subject == "baseline" else self.candidate_code
        return self._result(activity, code)


def _controlled_engine(
    project_root: Path,
    state_root: Path,
    *,
    baseline_code: int = 0,
    candidate_code: int = 0,
    run_code: int = 0,
) -> ControlPlaneEngine:
    engine = ControlPlaneEngine(project_root, state_root, POLICY)
    engine.executor.close()
    engine.executor = cast(
        Any, _ControlledExecutor(project_root, baseline_code, candidate_code, run_code)
    )
    return engine


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SELF_TEST.read_text(encoding="utf-8")))


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sqlite_persistence_and_idempotent_replay(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        first = engine.run(SELF_TEST)
        assert first["status"] == "closed"
        assert not (ROOT / "var/control_plane_self_test").exists()
    finally:
        engine.close()
    reopened = StateStore(state_root / "control_plane.sqlite3")
    try:
        assert reopened.summary("control_plane_self_test")["state"] == "CLOSED"
        assert reopened.summary("control_plane_self_test")["completed_activities"] == 3
    finally:
        reopened.close()
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        second = engine.run(SELF_TEST)
        assert second["status"] == "closed"
        assert second["summary"]["completed_activities"] == 3
    finally:
        engine.close()


def test_remove_is_bound_to_quarantined_inode_during_path_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("validated", encoding="utf-8")
    real_rename = os.rename
    raced = False

    def rename_then_substitute(*args: Any, **kwargs: Any) -> None:
        nonlocal raced
        real_rename(*args, **kwargs)
        if not raced and args[0] == "victim.txt":
            raced = True
            victim.write_text("substitute", encoding="utf-8")

    guard = FilesystemGuard(tmp_path)
    monkeypatch.setattr(os, "rename", rename_then_substitute)
    try:
        assert guard.remove("victim.txt", "file")
    finally:
        guard.close()
    assert raced
    assert victim.read_text(encoding="utf-8") == "substitute"


def test_atomic_publication_never_mutates_racing_hard_link(
    tmp_path: Path,
) -> None:
    target = tmp_path / "artifact.txt"
    target.write_text("old", encoding="utf-8")
    retained = tmp_path / "retained.txt"
    os.link(target, retained)
    guard = FilesystemGuard(tmp_path)
    try:
        guard.write_text("artifact.txt", "new")
    finally:
        guard.close()
    assert target.read_text(encoding="utf-8") == "new"
    assert retained.read_text(encoding="utf-8") == "old"


def test_external_capability_uses_closed_typed_sandbox_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = load_manifest(
        ROOT / "config/control_plane/campaigns/phase68_70_consolidated_capstone.json", ROOT
    )
    activity = next(
        item for item in manifest.activities if item.id == "phase68_recipient_replay_verification"
    )
    captured: dict[str, Any] = {}

    def completed(command: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(command=command, **kwargs)
        capability = executor.guard.resolve(activity)
        assert capability.script_fd is not None
        assert capability.script_fd not in kwargs["pass_fds"]
        assert f"/proc/self/fd/{capability.script_fd}" not in command
        assert capability.script_relative is not None
        target = str(Path("/run/upi_app_factory_project") / capability.script_relative)
        bind_index = command.index(target)
        assert command[bind_index - 2] == "--ro-bind-data"
        private_fd = int(command[bind_index - 1])
        assert private_fd in kwargs["pass_fds"]
        assert f"/proc/self/fd/{private_fd}" not in command
        expected = os.pread(capability.script_fd, os.fstat(capability.script_fd).st_size, 0)
        assert os.pread(private_fd, len(expected) + 1, 0) == expected
        required_seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        assert fcntl.fcntl(private_fd, fcntl.F_GET_SEALS) == required_seals
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "tools.factory_control_plane.executor.shutil.which",
        lambda *_a, **_k: "/usr/bin/bwrap",
    )
    monkeypatch.setattr("tools.factory_control_plane.executor.subprocess.run", completed)
    executor = CapabilityExecutor(ROOT)
    try:
        assert executor.run(activity).returncode == 0
        capability = executor.guard.resolve(activity)
        command = captured["command"]
        assert "--unshare-all" in command
        assert ("--ro-bind", "/", "/") not in tuple(zip(command, command[1:], command[2:]))
        assert capability.script_relative is not None
        assert str(Path("/run/upi_app_factory_project") / capability.script_relative) in command
        assert capability.script_fd not in captured["pass_fds"]
        seccomp_index = command.index("--seccomp")
        assert int(command[seccomp_index + 1]) in captured["pass_fds"]
    finally:
        executor.close()


def test_fresh_reconstructed_candidate_first_run_bootstrap(tmp_path: Path) -> None:
    index = tmp_path / "candidate.index"
    object_store = tmp_path / "objects"
    object_store.mkdir()
    git_directory = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    environment = {
        **os.environ,
        "GIT_INDEX_FILE": str(index),
        "GIT_OBJECT_DIRECTORY": str(object_store),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(Path(git_directory) / "objects"),
    }
    subprocess.run(["git", "read-tree", "HEAD"], cwd=ROOT, env=environment, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ROOT, env=environment, check=True)
    patch = subprocess.run(
        ["git", "diff", "--cached", "--binary", "HEAD"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
    ).stdout
    reconstructed = tmp_path / "candidate"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(reconstructed)],
        check=True,
    )
    subprocess.run(
        ["git", "apply", "--binary", "--whitespace=nowarn", "-"],
        cwd=reconstructed,
        input=patch,
        check=True,
    )
    assert not (reconstructed / "tmp").exists()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/phase68_70/test_consolidated_capstone.py::"
            "test_consolidated_runner_writes_truthful_isolated_summary",
        ],
        cwd=reconstructed,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_real_bwrap_absent_nested_write_root_bootstrap(tmp_path: Path) -> None:
    assert shutil.which("bwrap", path="/usr/bin:/bin") is not None, "real bwrap is required"
    source = tmp_path / "source"
    script = source / "scripts" / "write_nested.py"
    script.parent.mkdir(parents=True)
    script_text = (
        "from pathlib import Path\n"
        "root = Path('runtime/nested')\n"
        "root.joinpath('inside.txt').write_text('confined\\n', encoding='utf-8')\n"
        "try:\n"
        "    Path('outside.txt').write_text('escape', encoding='utf-8')\n"
        "except OSError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit(9)\n"
    )
    script.write_text(script_text, encoding="utf-8")
    registry = source / "config/control_plane/automatic_capabilities.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": ["runtime/nested"],
                "capabilities": [
                    {
                        "id": "nested_write",
                        "request_argv": ["capability:nested_write"],
                        "kind": "python_script",
                        "executable": "/usr/bin/python3",
                        "script": "scripts/write_nested.py",
                        "script_sha256": hashlib.sha256(script_text.encode()).hexdigest(),
                        "arguments": [],
                        "effects": ["write"],
                        "write_roots": ["runtime/nested"],
                        "environment": [],
                        "network": False,
                        "replace_write_root": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    activity = Activity(
        id="nested_write",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:nested_write",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=("runtime/nested",),
        digest="synthetic",
    )
    assert not (source / "runtime/nested").exists()
    executor = CapabilityExecutor(source)
    try:
        result = executor.run(activity)
    finally:
        executor.close()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (source / "runtime/nested/inside.txt").read_text(encoding="utf-8") == "confined\n"
    assert not (source / "outside.txt").exists()


def test_real_bwrap_executes_sealed_bytes_after_in_place_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert shutil.which("bwrap", path="/usr/bin:/bin") is not None, "real bwrap is required"
    source = tmp_path / "source"
    script = source / "scripts" / "sealed.py"
    script.parent.mkdir(parents=True)
    original = b"print('ORIGINAL')\n"
    mutated = b"print('MUTATED!')\n"
    assert len(original) == len(mutated)
    script.write_bytes(original)
    registry = source / "config/control_plane/automatic_capabilities.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": [],
                "capabilities": [
                    {
                        "id": "sealed_script",
                        "request_argv": ["capability:sealed_script"],
                        "kind": "python_script",
                        "executable": "/usr/bin/python3",
                        "script": "scripts/sealed.py",
                        "script_sha256": hashlib.sha256(original).hexdigest(),
                        "arguments": [],
                        "effects": ["read"],
                        "write_roots": [],
                        "environment": [],
                        "network": False,
                        "replace_write_root": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    activity = Activity(
        id="sealed_script",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:sealed_script",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=(),
        digest="synthetic",
    )
    real_run = subprocess.run
    mutated_during_launch = False

    def mutate_then_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal mutated_during_launch
        script.write_bytes(mutated)
        mutated_during_launch = True
        return real_run(*args, **kwargs)

    executor = CapabilityExecutor(source)
    monkeypatch.setattr("tools.factory_control_plane.executor.subprocess.run", mutate_then_run)
    try:
        result = executor.run(activity)
    finally:
        script.write_bytes(original)
        executor.close()
    assert mutated_during_launch
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "ORIGINAL\n"
    assert "MUTATED" not in result.stdout


def test_registered_script_pre_copy_source_drift_fails_closed_before_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    script = source / "scripts" / "sealed.py"
    script.parent.mkdir(parents=True)
    original = b"print('ORIGINAL')\n"
    mutated = b"print('MUTATED!')\n"
    assert len(original) == len(mutated)
    script.write_bytes(original)
    registry = source / "config/control_plane/automatic_capabilities.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": [],
                "capabilities": [
                    {
                        "id": "sealed_script",
                        "request_argv": ["capability:sealed_script"],
                        "kind": "python_script",
                        "executable": "/usr/bin/python3",
                        "script": "scripts/sealed.py",
                        "script_sha256": hashlib.sha256(original).hexdigest(),
                        "arguments": [],
                        "effects": ["read"],
                        "write_roots": [],
                        "environment": [],
                        "network": False,
                        "replace_write_root": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    activity = Activity(
        id="sealed_script",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:sealed_script",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=(),
        digest="synthetic",
    )
    real_sealed_script_fd = executor_module._sealed_script_fd
    subprocess_called = False

    def mutate_then_copy(capability: Any) -> int:
        script.write_bytes(mutated)
        return real_sealed_script_fd(capability)

    def record_subprocess(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal subprocess_called
        subprocess_called = True
        raise AssertionError("subprocess.run must not be called after registered script drift")

    monkeypatch.setattr(executor_module, "_sealed_script_fd", mutate_then_copy)
    monkeypatch.setattr("tools.factory_control_plane.executor.shutil.which", lambda *_a, **_k: "/usr/bin/bwrap")
    monkeypatch.setattr("tools.factory_control_plane.executor.subprocess.run", record_subprocess)
    executor = CapabilityExecutor(source)
    try:
        with pytest.raises(ControlPlaneError):
            executor.run(activity)
    finally:
        executor.close()
    assert not subprocess_called


def test_manifest_and_changed_activity_drift_rejected(tmp_path: Path) -> None:
    payload = _payload()
    manifest_path = _write(tmp_path, payload)
    state_root = tmp_path / "state"
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        assert engine.run(manifest_path)["status"] == "closed"
    finally:
        engine.close()
    payload["activities"][0]["timeout_seconds"] = 31
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    try:
        with pytest.raises(ControlPlaneError, match="manifest drift"):
            engine.run(manifest_path)
    finally:
        engine.close()


def test_changed_inputs_for_existing_activity_fail_closed(tmp_path: Path) -> None:
    manifest = load_manifest(SELF_TEST, ROOT)
    store = StateStore(tmp_path / "state.sqlite3")
    try:
        store.create_or_load_campaign(manifest, manifest.baseline)
        activity = manifest.activities[0]
        store.record_activity("control_plane_self_test", activity, "completed", {"ok": True})
        payload = _payload()
        payload["activities"][0]["timeout_seconds"] = 31
        changed = load_manifest(_write(tmp_path, payload), ROOT)
        with pytest.raises(ControlPlaneError, match="changed inputs"):
            store.activity_status("control_plane_self_test", changed.activities[0])
    finally:
        store.close()


def test_capability_executor_restrictions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    manifest = load_manifest(_write(tmp_path, payload), ROOT)
    executor = CapabilityExecutor(ROOT)
    bad_exe = manifest.activities[0]
    object.__setattr__(bad_exe, "argv", ("sh", "-c", "true"))
    with pytest.raises(ControlPlaneError):
        executor.run(bad_exe)
    bad_cwd = manifest.activities[1]
    object.__setattr__(bad_cwd, "cwd", "../")
    with pytest.raises(ControlPlaneError, match="escapes"):
        executor.run(bad_cwd)
    ok = manifest.activities[1]
    object.__setattr__(
        ok,
        "argv",
        ("python3", "-c", "import os; print(os.getenv('CONTROL_PLANE_TEST_ALLOWED'))"),
    )
    object.__setattr__(ok, "environment_allowlist", ("CONTROL_PLANE_TEST_ALLOWED",))
    with pytest.raises(ControlPlaneError, match="environment"):
        executor.run(ok)


@pytest.mark.parametrize(
    "argv",
    [
        ("git", "commit", "-m", "forbidden"),
        ("/usr/bin/git", "remote", "set-url", "origin", "invalid"),
        ("python3", "-c", "__import__('subprocess').run(['git', 'push'])"),
        ("python3", "-c", "import socket; socket.socket()"),
        ("python3", "-c", "getattr(__builtins__, '__import__')('subprocess')"),
        ("./python3", "-c", "print('substitute')"),
    ],
)
def test_capability_executor_denies_effect_aliases(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    manifest = load_manifest(SELF_TEST, ROOT)
    activity = manifest.activities[1]
    object.__setattr__(activity, "argv", argv)
    with pytest.raises(ControlPlaneError):
        CapabilityExecutor(ROOT).run(activity)


def test_capability_executor_enforces_declared_write_scope(tmp_path: Path) -> None:
    manifest = load_manifest(SELF_TEST, ROOT)
    activity = manifest.activities[0]
    escaped = tmp_path / "escaped.txt"
    object.__setattr__(
        activity,
        "argv",
        ("python3", "-c", f"from pathlib import Path; Path({str(escaped)!r}).write_text('x')"),
    )
    with pytest.raises(ControlPlaneError):
        CapabilityExecutor(ROOT).run(activity)
    assert not escaped.exists()


@pytest.mark.parametrize("name", ["PATH", "LD_PRELOAD", "PYTHONPATH", "HTTP_PROXY"])
def test_capability_executor_denies_mutable_environment(name: str) -> None:
    activity = load_manifest(SELF_TEST, ROOT).activities[1]
    object.__setattr__(activity, "environment_allowlist", (name,))
    with pytest.raises(ControlPlaneError, match="environment"):
        CapabilityExecutor(ROOT).run(activity)


def test_runtime_noise_protected_and_out_of_scope_denied_before_mutation(tmp_path: Path) -> None:
    guard = CapabilityExecutor(ROOT).guard
    with pytest.raises(ControlPlaneError, match="disposable root|protected"):
        guard.validate_runtime_noise(".git", (".git",))
    with pytest.raises(ControlPlaneError, match="campaign write scope"):
        guard.validate_runtime_noise("var/control_plane_self_test", ("README.md",))
    assert (ROOT / ".git").is_dir()


def test_failed_activity_incident_without_state_rollback(tmp_path: Path) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state", baseline_code=4, candidate_code=4)
    try:
        result = engine.run(SELF_TEST)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.BASELINE_DEFECT.value
        summary = engine.status("control_plane_self_test")
        assert summary["state"] == "ENGINEERING"
        assert summary["completed_activities"] == 1
        assert summary["incidents"] == 1
    finally:
        engine.close()


def test_failure_classification_repair_budget() -> None:
    assert consumes_repair_budget(FailureClass.PRODUCT_DEFECT)
    assert not consumes_repair_budget(FailureClass.POLICY_DENIAL)
    assert not consumes_repair_budget(FailureClass.TEST_DEFECT)
    assert not consumes_repair_budget(FailureClass.BASELINE_DEFECT)
    assert os.name


def _classification_manifest(
    tmp_path: Path,
    script: str,
    prerequisites: list[dict[str, Any]] | None = None,
    noise: list[dict[str, Any]] | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": "classification_case",
        "metadata": {"product": "UPI App Factory", "product_id": "upi_app_factory"},
        "baseline": "BASELINE_COMMIT",
        "objective": "Exercise validation classification.",
        "scope": {"allowed_write_paths": ["runtime"]},
        "budgets": {"engineering_repairs": 1, "activity_seconds": 60},
        "approvals": {"human": []},
        "validation_controls": {
            "trusted_prerequisites": prerequisites or [],
            "deterministic_runtime_noise": noise or [],
        },
        "activities": [
            {
                "id": "observe",
                "action": "run_tests",
                "kind": "verification",
                "risk": "LOW",
                "argv": ["python3", "-c", script],
                "dependencies": [],
                "target_state": "OFFLINE_VALIDATED",
                "timeout_seconds": 30,
                "cwd": ".",
                "environment_allowlist": [],
                "allowed_write_paths": [],
            }
        ],
    }
    return _write(tmp_path, payload)


def test_identical_baseline_failure_does_not_consume_repair_budget(tmp_path: Path) -> None:
    manifest_path = _classification_manifest(tmp_path, "raise SystemExit(7)")
    engine = _controlled_engine(tmp_path, tmp_path / "state", baseline_code=7, candidate_code=7)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.BASELINE_DEFECT.value
        assert result["consumes_repair_budget"] is False
    finally:
        engine.close()


def test_candidate_attributable_product_defect_consumes_repair_budget(tmp_path: Path) -> None:
    script = (
        "import os; "
        "raise SystemExit(0 if os.environ['UPI_APP_FACTORY_OBSERVATION_SUBJECT'] "
        "== 'baseline' else 5)"
    )
    manifest_path = _classification_manifest(tmp_path, script)
    engine = _controlled_engine(tmp_path, tmp_path / "state", baseline_code=0, candidate_code=5)
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.PRODUCT_DEFECT.value
        assert result["consumes_repair_budget"] is True
    finally:
        engine.close()


def test_missing_prerequisite_and_runtime_noise_are_control_plane_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "runtime/noise").mkdir(parents=True)
    manifest_path = _classification_manifest(
        tmp_path,
        "raise SystemExit(0)",
        prerequisites=[
            {
                "id": "missing_validation_fixture",
                "kind": "file",
                "path": "runtime/missing.txt",
                "hydrate": False,
            }
        ],
        noise=[
            {
                "id": "ignored_runtime_noise",
                "kind": "directory",
                "path": "runtime/noise",
            }
        ],
    )
    engine = _controlled_engine(tmp_path, tmp_path / "state")
    try:
        result = engine.run(manifest_path)
        assert result["status"] == "failed"
        assert result["failure_class"] == FailureClass.MISSING_PREREQUISITE.value
        evidence = tmp_path / "state/evidence/classification_case/control/reconcile.json"
        assert json.loads(evidence.read_text(encoding="utf-8"))["runtime_noise"][0][
            "removed"
        ]
    finally:
        engine.close()
    assert not (tmp_path / "runtime/noise").exists()


def test_real_bwrap_writable_root_hardlink_fails_closed_without_external_mutation(
    tmp_path: Path,
) -> None:
    assert shutil.which("bwrap", path="/usr/bin:/bin") is not None, "real bwrap is required"
    source = tmp_path / "source"
    external = tmp_path / "outside-authority.txt"
    external.write_text("UNCHANGED\n", encoding="utf-8")
    runtime = source / "runtime" / "nested"
    runtime.mkdir(parents=True)
    os.link(external, runtime / "alias.txt")

    script = source / "scripts" / "overwrite_alias.py"
    script.parent.mkdir(parents=True)
    script_text = (
        "from pathlib import Path\n"
        "Path('runtime/nested/alias.txt').write_text('MUTATED\\n', encoding='utf-8')\n"
    )
    script.write_text(script_text, encoding="utf-8")
    registry = source / "config/control_plane/automatic_capabilities.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": ["runtime/nested"],
                "capabilities": [
                    {
                        "id": "hardlink_write",
                        "request_argv": ["capability:hardlink_write"],
                        "kind": "python_script",
                        "executable": "/usr/bin/python3",
                        "script": "scripts/overwrite_alias.py",
                        "script_sha256": hashlib.sha256(script_text.encode()).hexdigest(),
                        "arguments": [],
                        "effects": ["write"],
                        "write_roots": ["runtime/nested"],
                        "environment": [],
                        "network": False,
                        "replace_write_root": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    activity = Activity(
        id="hardlink_write",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:hardlink_write",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=("runtime/nested",),
        digest="synthetic",
    )
    before = os.stat(external)
    executor = CapabilityExecutor(source)
    try:
        with pytest.raises(ControlPlaneError, match="private writable staging"):
            executor.run(activity)
    finally:
        executor.close()
    after = os.stat(external)
    assert external.read_text(encoding="utf-8") == "UNCHANGED\n"
    assert (after.st_dev, after.st_ino, after.st_size, after.st_nlink) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_nlink,
    )


def test_filesystem_guard_remove_missing_parent_is_idempotent(tmp_path: Path) -> None:
    guard = FilesystemGuard(tmp_path)
    try:
        assert guard.remove("var/control_plane_self_test", "directory") is False
        assert not (tmp_path / "var").exists()
    finally:
        guard.close()
