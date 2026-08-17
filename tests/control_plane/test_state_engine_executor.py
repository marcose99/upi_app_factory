from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane import executor as executor_module
from tools.factory_control_plane.common import ControlPlaneError, git_worktree_identity
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.evidence import write_control_envelope
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
        return ActivityResult(
            item.id, item.action, item.kind, code, "out", "err", "", "", "start", "finish"
        )

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
    if not (project_root / ".git").exists():
        subprocess.run(["git", "init", "-q", str(project_root)], check=True)
        subprocess.run(
            ["git", "-C", str(project_root), "config", "user.email", "fixture@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "config", "user.name", "Test Fixture"],
            check=True,
        )
        (project_root / ".gitignore").write_text("state/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project_root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-qm", "fixture"], check=True
        )
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


def test_engine_rejects_checkout_substitution_after_authority_load(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "input.txt").write_text("authorized\n", encoding="utf-8")
    engine = _controlled_engine(source, tmp_path / "state")
    displaced = tmp_path / "displaced"
    source.rename(displaced)
    source.mkdir()
    (source / "input.txt").write_text("substituted\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(source), "-c", "user.name=test", "-c",
            "user.email=test@example.invalid", "commit", "-qm", "substitute",
        ],
        check=True,
    )
    try:
        with pytest.raises(
            ControlPlaneError,
            match="authority descriptors were loaded",
        ):
            engine.run(SELF_TEST)
    finally:
        engine.close()


@pytest.mark.parametrize(
    ("state", "completed_count"),
    [
        (LifecycleState.ENGINEERING, 1),
        (LifecycleState.OFFLINE_VALIDATED, 2),
        (LifecycleState.CLEANED, 3),
    ],
)
def test_campaign_resumes_from_persisted_lifecycle(
    tmp_path: Path, state: LifecycleState, completed_count: int
) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    manifest = engine.validate(SELF_TEST)
    try:
        engine.store.create_or_load_campaign(manifest, engine._resolve_baseline(manifest))
        engine.store.set_state(manifest.campaign_id, state)
        for activity in manifest.activities[:completed_count]:
            engine.store.record_activity(
                manifest.campaign_id, activity, "completed", {"returncode": 0}
            )
            write_control_envelope(
                engine.state_root,
                manifest.campaign_id,
                f"activity_candidate_identity_{activity.id}",
                git_worktree_identity(ROOT),
            )
        result = engine.run(SELF_TEST)
        assert result["status"] == "closed"
        assert result["summary"]["completed_activities"] == 3
    finally:
        engine.close()


def test_resume_preserves_completed_self_test_output(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    engine = ControlPlaneEngine(ROOT, state_root, POLICY)
    manifest = engine.validate(SELF_TEST)
    artifact = ROOT / "var/control_plane_self_test/artifact.txt"
    try:
        engine.store.create_or_load_campaign(manifest, engine._resolve_baseline(manifest))
        engine.store.set_state(manifest.campaign_id, LifecycleState.ENGINEERING)
        activity = manifest.activities[0]
        engine.executor.filesystem.mkdir("var/control_plane_self_test")
        engine.executor.filesystem.write_text(
            "var/control_plane_self_test/artifact.txt",
            "upi_app_factory control plane self-test\n",
        )
        engine.store.record_activity(
            manifest.campaign_id, activity, "completed", {"returncode": 0}
        )
        write_control_envelope(
            state_root,
            manifest.campaign_id,
            f"activity_candidate_identity_{activity.id}",
            git_worktree_identity(ROOT),
        )
        # Model a process interruption after the producer durably completed.
        engine.close()
        engine = ControlPlaneEngine(ROOT, state_root, POLICY)
        result = engine.run(SELF_TEST)
        assert result["status"] == "closed"
        assert result["summary"]["completed_activities"] == 3
        assert not artifact.exists()
    finally:
        engine.close()


def test_sealed_summary_truthfully_records_finalizing_boundary(tmp_path: Path) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    try:
        result = engine.run(SELF_TEST)
        archive_path = Path(result["sealed"]["archive"])
        import tarfile

        with tarfile.open(archive_path, "r:gz") as archive:
            stream = archive.extractfile("summary.json")
            assert stream is not None
            summary = json.loads(stream.read())
        assert summary["summary"]["state"] == "FINALIZING"
    finally:
        engine.close()


def test_public_sealing_rejects_unknown_open_and_traversal_campaigns(tmp_path: Path) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    manifest = engine.validate(SELF_TEST)
    try:
        engine.store.create_or_load_campaign(manifest, engine._resolve_baseline(manifest))
        for campaign_id in (manifest.campaign_id, "unknown", "../../outside"):
            with pytest.raises(ControlPlaneError):
                engine.seal_evidence(campaign_id)
    finally:
        engine.close()


def test_seal_failure_leaves_campaign_finalizing_and_retry_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    real_seal = engine.seal_evidence
    calls = 0

    def fail_once(campaign_id: str) -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected finalization failure")
        return real_seal(campaign_id)

    monkeypatch.setattr(engine, "seal_evidence", fail_once)
    try:
        with pytest.raises(OSError, match="injected finalization failure"):
            engine.run(SELF_TEST)
        assert engine.store.summary("control_plane_self_test")["state"] == "FINALIZING"
        assert engine.run(SELF_TEST)["status"] == "closed"
    finally:
        engine.close()


def test_published_seal_recovers_to_closed_and_closed_status_requires_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    real_set_state = engine.store.set_state
    interrupted = False

    def interrupt_before_closed(campaign_id: str, target: LifecycleState) -> None:
        nonlocal interrupted
        if target is LifecycleState.CLOSED and not interrupted:
            interrupted = True
            raise OSError("injected pre-close crash")
        real_set_state(campaign_id, target)

    monkeypatch.setattr(engine.store, "set_state", interrupt_before_closed)
    try:
        with pytest.raises(OSError, match="injected pre-close crash"):
            engine.run(SELF_TEST)
        assert engine.store.summary("control_plane_self_test")["state"] == "FINALIZING"
        assert engine.run(SELF_TEST)["status"] == "closed"
        shutil.rmtree(tmp_path / "state/sealed/control_plane_self_test.seal")
        with pytest.raises(ControlPlaneError, match="seal is missing"):
            engine.status("control_plane_self_test")
    finally:
        engine.close()


def test_published_seal_cannot_be_replaced_or_detached_from_evidence(
    tmp_path: Path,
) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    try:
        result = engine.run(SELF_TEST)
        archive = Path(result["sealed"]["archive"])
        before = hashlib.sha256(archive.read_bytes()).hexdigest()
        evidence = (
            tmp_path
            / "state/evidence/control_plane_self_test/control/execution_order.json"
        )
        evidence.write_text("{}\n", encoding="utf-8")
        with pytest.raises(ControlPlaneError):
            engine.seal_evidence("control_plane_self_test")
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == before
    finally:
        engine.close()


def test_finalizing_without_prebound_identity_fails_closed(tmp_path: Path) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    manifest = engine.validate(SELF_TEST)
    try:
        baseline = engine._resolve_baseline(manifest)
        engine.store.create_or_load_campaign(manifest, baseline)
        engine.store.set_state(manifest.campaign_id, LifecycleState.FINALIZING)
        with pytest.raises(ControlPlaneError, match="no bound candidate identity"):
            engine.run(SELF_TEST)
    finally:
        engine.close()


def test_finalizing_resume_rejects_executable_mode_drift(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    executable = project / "factoryctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    engine = _controlled_engine(project, tmp_path / "state")
    manifest = engine.validate(SELF_TEST)
    try:
        baseline = engine._resolve_baseline(manifest)
        engine.store.create_or_load_campaign(manifest, baseline)
        write_control_envelope(
            engine.state_root,
            manifest.campaign_id,
            "final_candidate_identity",
            git_worktree_identity(project),
        )
        engine.store.set_state(manifest.campaign_id, LifecycleState.FINALIZING)
        executable.chmod(0o644)
        with pytest.raises(ControlPlaneError, match="candidate identity drifted"):
            engine.run(SELF_TEST)
    finally:
        engine.close()


def test_snapshot_preserves_executable_mode_and_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    executable = source / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "run.sh"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"],
        cwd=source,
        check=True,
    )

    identity = git_worktree_identity(source)
    snapshot = tmp_path / "snapshot"
    assert executor_module._materialize_repository_snapshot(source, snapshot, ()) == identity
    assert snapshot.joinpath("run.sh").stat().st_mode & stat.S_IXUSR


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
    real_run = subprocess.run

    def completed(command: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[0] == "git":
            return real_run(command, **kwargs)
        captured.update(command=command, **kwargs)
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["close_fds"] is True
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
            fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        )
        assert fcntl.fcntl(private_fd, fcntl.F_GET_SEALS) == required_seals
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "tools.factory_control_plane.host_runtime.shutil.which",
        lambda *_a, **_k: "/usr/bin/bwrap",
    )
    monkeypatch.setattr("tools.factory_control_plane.executor.subprocess.run", completed)
    executor = CapabilityExecutor(ROOT)
    try:
        assert executor.run(activity).returncode == 0
        capability = executor.guard.resolve(activity)
        command = captured["command"]
        assert "--unshare-all" in command
        assert "--share-net" in command
        assert command.index("--share-net") > command.index("--unshare-all")
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
                        "executable": "python3",
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
                        "executable": "python3",
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


def test_revision_bound_snapshot_excludes_ignored_secret_from_modified_import(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".gitignore").write_text(".env\n", encoding="utf-8")
    helper = source / "helper.py"
    helper.write_text("print('ORIGINAL')\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", ".gitignore", "helper.py"], cwd=source, check=True)
    (source / ".env").write_text("TOKEN=ignored-credential\n", encoding="utf-8")
    helper.write_text(
        "from pathlib import Path\n"
        "print(Path('.env').read_text() if Path('.env').exists() else 'SECRET_UNAVAILABLE')\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot"
    executor_module._materialize_repository_snapshot(source, snapshot, ())
    completed = subprocess.run(
        [sys.executable, "helper.py"],
        cwd=snapshot,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "SECRET_UNAVAILABLE\n"
    assert "ignored-credential" not in completed.stdout
    assert not (snapshot / ".env").exists()


def test_revision_bound_snapshot_includes_untracked_candidate_input(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", ".gitignore"], cwd=source, check=True)
    (source / "required.py").write_text("print('UNTRACKED_VERIFIED')\n", encoding="utf-8")
    (source / "ignored.txt").write_text("secret", encoding="utf-8")

    snapshot = tmp_path / "snapshot"
    executor_module._materialize_repository_snapshot(source, snapshot, ())
    completed = subprocess.run(
        [sys.executable, "required.py"],
        cwd=snapshot,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "UNTRACKED_VERIFIED\n"
    assert not (snapshot / "ignored.txt").exists()


def test_snapshot_denies_candidate_set_drift_before_digest_and_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    entrypoint = source / "entrypoint.py"
    entrypoint.write_text("import helper\nprint('AUTHORIZED')\n", encoding="utf-8")
    helper = source / "helper.py"
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "entrypoint.py"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"],
        cwd=source,
        check=True,
    )

    real_candidate_paths = executor_module.git_candidate_paths
    real_copy_directory = executor_module._copy_snapshot_directory
    inserted = False
    removed = False

    def insert_shadow_before_enumeration(root: Path) -> tuple[bytes, ...]:
        nonlocal inserted
        if not inserted:
            helper.write_text("print('ATTACKER-CONTROLLED')\n", encoding="utf-8")
            inserted = True
        return real_candidate_paths(root)

    def copy_then_remove_shadow(*args: Any, **kwargs: Any) -> None:
        nonlocal removed
        real_copy_directory(*args, **kwargs)
        if not removed:
            helper.unlink()
            removed = True

    monkeypatch.setattr(executor_module, "git_candidate_paths", insert_shadow_before_enumeration)
    monkeypatch.setattr(executor_module, "_copy_snapshot_directory", copy_then_remove_shadow)
    snapshot = tmp_path / "snapshot"
    capability_executed = False
    with pytest.raises(ControlPlaneError, match="private writable staging"):
        executor_module._materialize_repository_snapshot(source, snapshot, ())
        capability_executed = True

    assert inserted and removed
    assert not capability_executed
    assert not snapshot.exists()


def test_candidate_identity_represents_tracked_deletion(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    obsolete = source / "obsolete.txt"
    obsolete.write_text("remove me\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "obsolete.txt"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"],
        cwd=source,
        check=True,
    )
    before = git_worktree_identity(source)
    obsolete.unlink()
    deleted = git_worktree_identity(source)
    assert deleted["head"] == before["head"]
    assert deleted["tree_sha256"] != before["tree_sha256"]


def test_writable_stage_uses_snapshot_not_ignored_live_content(tmp_path: Path) -> None:
    source = tmp_path / "source"
    writable = source / "tmp"
    writable.mkdir(parents=True)
    (source / ".gitignore").write_text("tmp/secret.txt\n", encoding="utf-8")
    (writable / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    (writable / "secret.txt").write_text("ignored-secret\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", ".gitignore", "tmp/tracked.txt"], cwd=source, check=True)
    snapshot = tmp_path / "snapshot"
    executor_module._materialize_repository_snapshot(source, snapshot, ())

    live_guard = FilesystemGuard(source)
    snapshot_guard = FilesystemGuard(snapshot)
    root = live_guard.directory("tmp")
    stage = live_guard.private_stage(root, ".stage", copy_existing=False)
    captured = snapshot_guard.directory("tmp")
    try:
        snapshot_guard.copy_tree(captured, stage)
        live_guard.promote_many(((root, ".stage"),))
    finally:
        captured.close()
        stage.close()
        root.close()
        snapshot_guard.close()
        live_guard.close()
    assert (writable / "tracked.txt").read_text(encoding="utf-8") == "candidate\n"
    assert not (writable / "secret.txt").exists()


def test_materialized_identity_detects_aba_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "input.txt"
    target.write_text("AUTHORIZED\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "input.txt"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"],
        cwd=source,
        check=True,
    )
    authorized = git_worktree_identity(source)
    real_copy = executor_module._copy_snapshot_file

    def substitute_then_restore(*args: Any, **kwargs: Any) -> bytes:
        target.write_text("SUBSTITUTED\n", encoding="utf-8")
        try:
            return real_copy(*args, **kwargs)
        finally:
            target.write_text("AUTHORIZED\n", encoding="utf-8")

    monkeypatch.setattr(executor_module, "_copy_snapshot_file", substitute_then_restore)
    materialized = executor_module._materialize_repository_snapshot(
        source, tmp_path / "snapshot", ()
    )
    assert materialized != authorized
    assert git_worktree_identity(source) == authorized


def test_internal_verifier_reads_the_supplied_execution_root(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    (baseline / "var/control_plane_self_test").mkdir(parents=True)
    (candidate / "var/control_plane_self_test").mkdir(parents=True)
    (baseline / "var/control_plane_self_test/artifact.txt").write_text(
        "baseline bytes\n", encoding="utf-8"
    )
    (candidate / "var/control_plane_self_test/artifact.txt").write_text(
        "upi_app_factory control plane self-test\n", encoding="utf-8"
    )
    activity = load_manifest(SELF_TEST, ROOT).activities[1]
    executor = CapabilityExecutor(ROOT)
    try:
        baseline_result = executor._run_internal(
            activity, "self_test_verify", baseline
        )
        candidate_result = executor._run_internal(
            activity, "self_test_verify", candidate
        )
    finally:
        executor.close()
    assert baseline_result.returncode == 1
    assert candidate_result.returncode == 0


@pytest.mark.parametrize(
    "capability_id", ["self_test_verify", "phase69_checkpoint", "phase68_70_checkpoint"]
)
def test_internal_verifier_treats_absent_artifact_as_failed_observation(
    tmp_path: Path, capability_id: str
) -> None:
    execution_root = tmp_path / "empty"
    execution_root.mkdir()
    activity = load_manifest(SELF_TEST, ROOT).activities[1]
    executor = CapabilityExecutor(ROOT)
    try:
        result = executor._run_internal(activity, capability_id, execution_root)
    finally:
        executor.close()
    assert result.returncode == 1


@pytest.mark.parametrize("mutation", ["change", "add", "remove"])
def test_closed_recovery_rejects_live_evidence_drift(
    tmp_path: Path, mutation: str
) -> None:
    engine = _controlled_engine(ROOT, tmp_path / "state")
    try:
        assert engine.run(SELF_TEST)["status"] == "closed"
        evidence_root = tmp_path / "state/evidence/control_plane_self_test"
        target = evidence_root / "control/execution_order.json"
        if mutation == "change":
            target.write_text("{}\n", encoding="utf-8")
        elif mutation == "add":
            (evidence_root / "unexpected.json").write_text("{}\n", encoding="utf-8")
        else:
            target.unlink()
        with pytest.raises(ControlPlaneError):
            engine.run(SELF_TEST)
    finally:
        engine.close()


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, False),
        (
            {
                "UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1",
                "GITHUB_ACTIONS": "true",
                "CI": "true",
            },
            True,
        ),
    ],
)
def test_github_ci_share_net_gate_is_deterministic(
    environment: dict[str, str], expected: bool
) -> None:
    assert executor_module._github_ci_share_host_network_namespace(environment) is expected


@pytest.mark.parametrize(
    "environment",
    [
        {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "0"},
        {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1"},
        {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1", "GITHUB_ACTIONS": "true"},
        {"UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET": "1", "CI": "true"},
    ],
)
def test_github_ci_share_net_gate_rejects_partial_or_invalid_opt_in(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ControlPlaneError):
        executor_module._github_ci_share_host_network_namespace(environment)


def test_isolation_argv_is_exact_for_default_and_github_fallback() -> None:
    assert executor_module.build_isolation_argv(False, 17) == (
        "--unshare-all",
        "--share-net",
        "--seccomp",
        "17",
    )
    assert executor_module.build_isolation_argv(True, 17) == (
        "--unshare-all",
        "--share-net",
        "--seccomp",
        "17",
    )


def test_github_ci_share_net_mode_is_denied_outside_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET", "1")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(ControlPlaneError, match="denied outside GitHub Actions"):
        executor_module._github_ci_share_host_network_namespace()


def test_real_bwrap_github_ci_share_net_mode_keeps_network_seccomp_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert shutil.which("bwrap", path="/usr/bin:/bin") is not None, "real bwrap is required"
    monkeypatch.setenv("UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("CI", "true")

    source = tmp_path / "source"
    script = source / "scripts" / "network_probe.py"
    script.parent.mkdir(parents=True)
    script_text = (
        "import socket\n"
        "try:\n"
        "    socket.socket()\n"
        "except OSError as exc:\n"
        "    print(f'NETWORK_DENIED:{exc.errno}')\n"
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
                "disposable_roots": [],
                "capabilities": [
                    {
                        "id": "network_probe",
                        "request_argv": ["capability:network_probe"],
                        "kind": "python_script",
                        "executable": "python3",
                        "script": "scripts/network_probe.py",
                        "script_sha256": hashlib.sha256(script_text.encode()).hexdigest(),
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
        id="network_probe",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:network_probe",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=(),
        digest="synthetic",
    )
    executor = CapabilityExecutor(source)
    try:
        result = executor.run(activity)
    finally:
        executor.close()
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("NETWORK_DENIED:")


def test_real_bwrap_does_not_inherit_preexisting_stdin_authority(tmp_path: Path) -> None:
    assert shutil.which("bwrap", path="/usr/bin:/bin") is not None
    source = tmp_path / "source"
    script = source / "scripts" / "stdin_probe.py"
    script.parent.mkdir(parents=True)
    script_text = "import os\ndata=os.read(0,64)\nprint(f'STDIN_BYTES:{len(data)}')\nraise SystemExit(9 if data else 0)\n"
    script.write_text(script_text, encoding="utf-8")
    registry = source / "config/control_plane/automatic_capabilities.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "disposable_roots": [],
                "capabilities": [
                    {
                        "id": "stdin_probe",
                        "request_argv": ["capability:stdin_probe"],
                        "kind": "python_script",
                        "executable": "python3",
                        "script": "scripts/stdin_probe.py",
                        "script_sha256": hashlib.sha256(script_text.encode()).hexdigest(),
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
        id="stdin_probe",
        action="execute_engineering",
        kind="execution",
        risk="LOW",
        argv=("capability:stdin_probe",),
        dependencies=(),
        target_state=LifecycleState.ENGINEERING,
        timeout_seconds=30,
        cwd=".",
        environment_allowlist=(),
        allowed_write_paths=(),
        digest="synthetic",
    )
    inherited, peer = os.pipe()
    saved = os.dup(0)
    try:
        os.dup2(inherited, 0)
        os.write(peer, b"PREEXISTING_STDIN_AUTHORITY")
        executor = CapabilityExecutor(source)
        try:
            result = executor.run(activity)
        finally:
            executor.close()
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(inherited)
        os.close(peer)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "STDIN_BYTES:0\n"


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
                        "executable": "python3",
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
    monkeypatch.setattr(
        "tools.factory_control_plane.host_runtime.shutil.which", lambda *_a, **_k: "/usr/bin/bwrap"
    )
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
def test_capability_executor_denies_effect_aliases(tmp_path: Path, argv: tuple[str, ...]) -> None:
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
        assert json.loads(evidence.read_text(encoding="utf-8"))["runtime_noise"][0]["removed"]
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
                        "executable": "python3",
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
