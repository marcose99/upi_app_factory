from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tools.factory_control_plane.capability_guard import (
    CapabilityGuard,
    ResolvedCapability,
    sanitized_environment,
)
from tools.factory_control_plane.common import (
    ControlPlaneError,
    git_candidate_index_modes,
    git_candidate_paths as git_candidate_paths,
    git_head,
    resolve_under_root,
    sha256_text,
    utc_now,
)
from tools.factory_control_plane.manifest import Activity
from tools.factory_control_plane.fs_guard import DirectoryHandle, FilesystemGuard
from tools.factory_control_plane.host_runtime import detect_isolation_runtime


_SNAPSHOT_IGNORED_ROOTS = frozenset(
    {".git", ".agents", ".codex", "__pycache__", ".mypy_cache", ".pytest_cache"}
)
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
_SCRIPT_SEALS = (
    fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
)

_PRIVATE_WRITE_STAGE = ".capability-private-staging"


@dataclass(frozen=True)
class _CandidateManifest:
    head: str | None
    entries: tuple[tuple[bytes, bytes], ...]

    @property
    def paths(self) -> tuple[bytes, ...]:
        return tuple(raw for raw, _mode in self.entries)


def _candidate_manifest(source: Path) -> _CandidateManifest:
    """Capture a stable candidate membership/index manifest.

    Git exposes the index and untracked worktree membership through separate
    queries. Bracketing and repeating those queries makes any observable drift
    fail closed instead of combining values from different candidate states.
    """
    try:
        head_before = git_head(source)
    except ControlPlaneError:
        head_before = None
    modes_before = git_candidate_index_modes(source)
    paths_before = git_candidate_paths(source)
    try:
        head_after = git_head(source)
    except ControlPlaneError:
        head_after = None
    modes_after = git_candidate_index_modes(source)
    paths_after = git_candidate_paths(source)
    if (
        head_before != head_after
        or modes_before != modes_after
        or paths_before != paths_after
        or not set(modes_before).issubset(paths_before)
    ):
        raise ControlPlaneError("candidate manifest changed during capture")
    return _CandidateManifest(
        head=head_before,
        entries=tuple(
            (raw, modes_before.get(raw, b"UNTRACKED")) for raw in paths_before
        ),
    )


def _same_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (first.st_dev, first.st_ino, first.st_mode) == (
        second.st_dev,
        second.st_ino,
        second.st_mode,
    )


def _stable_file_metadata(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _materialize_repository_snapshot(
    source: Path, destination: Path, omitted_roots: tuple[Path, ...]
) -> dict[str, str] | None:
    """Materialize revision-bound inputs using only pinned, no-follow descriptors."""
    omitted = {path.parts for path in omitted_roots}
    manifest = _revision_bound_manifest(source)
    included = None if manifest is None else {
        tuple(Path(os.fsdecode(raw)).parts) for raw in manifest.paths
    }
    staging = destination.with_name(f".{destination.name}.staging")
    source_fd = -1
    staging_fd = -1
    try:
        source_fd = os.open(source, _DIRECTORY_FLAGS)
        os.mkdir(staging, mode=0o700)
        staging_fd = os.open(staging, _DIRECTORY_FLAGS)
        captured: dict[bytes, tuple[bytes, int]] = {}
        _copy_snapshot_directory(source_fd, staging_fd, (), omitted, included, captured)
        if manifest is None:
            os.rename(staging, destination)
            return None
        if _candidate_manifest(source) != manifest:
            raise RuntimeError("candidate manifest changed during snapshot")
        expected_captured = {
            raw for raw in manifest.paths if os.path.lexists(source / os.fsdecode(raw))
        }
        if set(captured) != expected_captured:
            raise RuntimeError("snapshot entries do not match candidate manifest")
        digest = hashlib.sha256()
        for raw, index_mode in manifest.entries:
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(raw)
            digest.update(len(index_mode).to_bytes(8, "big"))
            digest.update(index_mode)
            captured_file = captured.get(raw)
            if captured_file is None:
                digest.update(b"D")
            else:
                payload, mode = captured_file
                digest.update(b"F")
                digest.update(stat.S_IMODE(mode).to_bytes(4, "big"))
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
        if manifest.head is None:
            # Synthetic repositories used to exercise snapshot filtering may
            # have an index but no commit and therefore no candidate identity.
            if _candidate_manifest(source) != manifest:
                raise RuntimeError("candidate manifest changed before publication")
            os.rename(staging, destination)
            return None
        identity = {"head": manifest.head, "tree_sha256": digest.hexdigest()}
        if _candidate_manifest(source) != manifest:
            raise RuntimeError("candidate manifest changed before publication")
        os.rename(staging, destination)
        return identity
    except (OSError, RuntimeError) as exc:
        raise ControlPlaneError(
            "repository snapshot source is unsafe or changed; private writable staging denied"
        ) from exc
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if source_fd >= 0:
            os.close(source_fd)


def _revision_bound_manifest(source: Path) -> _CandidateManifest | None:
    """Return exact candidate inputs, or None for an already materialized archive.

    Candidate execution receives tracked and untracked non-ignored bytes, the
    same set covered by ``git_worktree_identity``. Ignored workspace bytes are
    never copied.
    Baseline subjects and small synthetic capability fixtures have no .git and
    are already explicit materializations owned by their caller.
    """
    if not (source / ".git").exists():
        return None
    return _candidate_manifest(source)


def _copy_snapshot_directory(
    source_fd: int,
    destination_fd: int,
    relative: tuple[str, ...],
    omitted: set[tuple[str, ...]],
    included: set[tuple[str, ...]] | None,
    captured: dict[bytes, tuple[bytes, int]],
) -> None:
    for name in sorted(os.listdir(source_fd)):
        child_relative = (*relative, name)
        if name in _SNAPSHOT_IGNORED_ROOTS or child_relative in omitted:
            continue
        if included is not None and not any(
            path == child_relative or path[: len(child_relative)] == child_relative
            for path in included
        ):
            continue
        before = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=source_fd)
            destination_child_fd = -1
            try:
                opened = os.fstat(child_fd)
                if not _same_identity(before, opened):
                    raise RuntimeError("directory identity changed before traversal")
                os.mkdir(name, mode=0o700, dir_fd=destination_fd)
                destination_child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=destination_fd)
                _copy_snapshot_directory(
                    child_fd, destination_child_fd, child_relative, omitted, included, captured
                )
                after = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
                if not _same_identity(opened, after):
                    raise RuntimeError("directory identity changed during traversal")
            finally:
                if destination_child_fd >= 0:
                    os.close(destination_child_fd)
                os.close(child_fd)
        elif stat.S_ISREG(before.st_mode):
            payload = _copy_snapshot_file(source_fd, destination_fd, name, before)
            captured[os.fsencode(Path(*child_relative).as_posix())] = (
                payload,
                before.st_mode,
            )
        else:
            raise RuntimeError("snapshot entry has a forbidden type")


def _copy_snapshot_file(
    source_fd: int, destination_fd: int, name: str, before: os.stat_result
) -> bytes:
    if before.st_nlink != 1:
        raise RuntimeError("snapshot file has an unsafe hard-link count")
    input_fd = os.open(name, _FILE_FLAGS, dir_fd=source_fd)
    output_fd = -1
    try:
        opened = os.fstat(input_fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise RuntimeError("snapshot file identity is unsafe")
        if not _same_identity(before, opened):
            raise RuntimeError("snapshot file identity changed before read")
        output_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=destination_fd,
        )
        chunks: list[bytes] = []
        while data := os.read(input_fd, 1024 * 1024):
            chunks.append(data)
            view = memoryview(data)
            while view:
                written = os.write(output_fd, view)
                if written <= 0:
                    raise RuntimeError("snapshot destination write did not progress")
                view = view[written:]
        after_read = os.fstat(input_fd)
        current = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        if _stable_file_metadata(opened) != _stable_file_metadata(after_read):
            raise RuntimeError("snapshot file mutated during read")
        if not _same_identity(opened, current) or current.st_nlink != 1:
            raise RuntimeError("snapshot file entry changed during read")
        os.fchmod(output_fd, 0o700 if opened.st_mode & stat.S_IXUSR else 0o600)
        return b"".join(chunks)
    finally:
        if output_fd >= 0:
            os.close(output_fd)
        os.close(input_fd)


def _sealed_script_fd(capability: ResolvedCapability) -> int:
    """Copy a registered script descriptor into a verified, immutable memfd."""
    source_fd = capability.script_fd
    expected_digest = capability.script_sha256
    if source_fd is None or expected_digest is None:
        raise ControlPlaneError("registered script contract is incomplete")
    private_fd = -1
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("registered script descriptor is not a regular file")
        private_fd = os.memfd_create(
            "upi-private-script", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING
        )
        digest = hashlib.sha256()
        offset = 0
        while data := os.pread(source_fd, 1024 * 1024, offset):
            digest.update(data)
            view = memoryview(data)
            while view:
                written = os.write(private_fd, view)
                if written <= 0:
                    raise RuntimeError("private script copy did not progress")
                view = view[written:]
            offset += len(data)
        after = os.fstat(source_fd)
        if _stable_file_metadata(before) != _stable_file_metadata(after):
            raise RuntimeError("registered script mutated during private copy")
        if digest.hexdigest() != expected_digest:
            raise RuntimeError("private script digest does not match registration")
        fcntl.fcntl(private_fd, fcntl.F_ADD_SEALS, _SCRIPT_SEALS)
        if fcntl.fcntl(private_fd, fcntl.F_GET_SEALS) != _SCRIPT_SEALS:
            raise RuntimeError("private script seals could not be verified")
        os.lseek(private_fd, 0, os.SEEK_SET)
        return private_fd
    except (OSError, RuntimeError) as exc:
        if private_fd >= 0:
            os.close(private_fd)
        raise ControlPlaneError("registered script could not be copied and sealed") from exc


@dataclass(frozen=True)
class ActivityResult:
    activity_id: str
    action: str
    kind: str
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout: str
    stderr: str
    started_at: str
    finished_at: str
    authority_digests: dict[str, str] | None = None

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "activity_id": self.activity_id,
            "action": self.action,
            "kind": self.kind,
            "returncode": self.returncode,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        if self.authority_digests is not None:
            record["authority_digests"] = self.authority_digests
        return record


@dataclass(frozen=True)
class ExecutionPlan:
    """The single inspectable contract consumed by subprocess.run."""

    command: tuple[str, ...]
    cwd: str
    environment: dict[str, str]
    pass_fds: tuple[int, ...]
    stdin: int
    close_fds: bool
    timeout_seconds: int
    application_argv: tuple[str, ...]
    sandbox_project: str
    output_root: str | None
    network_namespace: bool
    seccomp_fd: int


def build_application_argv(
    capability: ResolvedCapability,
    project_root: Path,
    sandbox_project: Path,
    script_sandbox_path: Path | None,
) -> list[str]:
    """Build the executable argv used by the sandboxed subprocess."""
    if capability.executable is None:
        raise ControlPlaneError("external capability has no executable")
    application_argv = [str(capability.executable)]
    if capability.kind == "python_script":
        if script_sandbox_path is None:
            raise ControlPlaneError("Python capability has no pinned script binding")
        application_argv.append(str(script_sandbox_path))
    application_argv.extend(capability.arguments)
    for index, value in enumerate(application_argv[1:], start=1):
        path = Path(value)
        if path.is_absolute() and path.is_relative_to(project_root):
            application_argv[index] = str(sandbox_project / path.relative_to(project_root))
    return application_argv


_GITHUB_CI_SHARE_NET_ENV = "UPI_APP_FACTORY_GITHUB_CI_BWRAP_SHARE_NET"
_NETWORK_DENY_SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "io_uring_setup", "io_uring_enter", "io_uring_register", "bpf",
)


def _github_ci_share_host_network_namespace(
    environment: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if environment is None else environment
    value = source.get(_GITHUB_CI_SHARE_NET_ENV)
    if value is None:
        return False
    if value != "1":
        raise ControlPlaneError("GitHub CI Bubblewrap network compatibility flag is invalid")
    if source.get("GITHUB_ACTIONS") != "true" or source.get("CI") != "true":
        raise ControlPlaneError(
            "GitHub CI Bubblewrap network compatibility mode is denied outside GitHub Actions"
        )
    return True


def build_isolation_argv(_share_network: bool, seccomp_fd: int) -> tuple[str, ...]:
    """Build a portable no-network sandbox using a payload seccomp filter.

    Some nested/containerized Linux hosts cannot initialize a fresh network
    namespace. Sharing the namespace lets Bubblewrap finish setup; the filter
    still denies network syscalls to the executed capability.
    """
    return ("--unshare-all", "--share-net", "--seccomp", str(seccomp_fd))


class CapabilityExecutor:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.guard = CapabilityGuard(self.project_root)
        self.filesystem = FilesystemGuard(self.project_root)

    def close(self) -> None:
        self.guard.close()
        self.filesystem.close()

    def run(
        self, activity: Activity, expected_identity: dict[str, str] | None = None
    ) -> ActivityResult:
        return self._run(activity, {}, expected_identity=expected_identity)

    def observe(
        self,
        activity: Activity,
        subject: str,
        reference: str,
        expected_identity: dict[str, str] | None = None,
    ) -> ActivityResult:
        return self._run(
            activity,
            {
                "UPI_APP_FACTORY_OBSERVATION_SUBJECT": subject,
                "UPI_APP_FACTORY_OBSERVATION_REF": reference,
            },
            expected_identity=expected_identity,
        )

    def observe_at(
        self,
        activity: Activity,
        subject: str,
        reference: str,
        subject_root: Path,
    ) -> ActivityResult:
        """Execute an observation against an independently materialized subject."""
        return self._run(
            activity,
            {
                "UPI_APP_FACTORY_OBSERVATION_SUBJECT": subject,
                "UPI_APP_FACTORY_OBSERVATION_REF": reference,
            },
            subject_root,
        )

    def _run(
        self,
        activity: Activity,
        extra_env: dict[str, str],
        subject_root: Path | None = None,
        expected_identity: dict[str, str] | None = None,
    ) -> ActivityResult:
        execution_root = self.project_root if subject_root is None else subject_root.resolve()
        capability = self.guard.resolve(activity)
        for value in activity.argv:
            if "\x00" in value or "\n" in value:
                raise ControlPlaneError("argv contains forbidden control data")
        cwd = resolve_under_root(execution_root, activity.cwd)
        env = sanitized_environment(activity.environment_allowlist)
        env.update(extra_env)
        if capability.kind == "internal" and expected_identity is not None:
            with tempfile.TemporaryDirectory(
                prefix="upi_internal_observation_"
            ) as observation_directory:
                captured_root = Path(observation_directory) / "project"
                captured_identity = _materialize_repository_snapshot(
                    execution_root, captured_root, ()
                )
                if captured_identity != expected_identity:
                    raise ControlPlaneError(
                        "materialized candidate does not match authorized identity"
                    )
                # Internal verifiers are trusted code and may inspect governed
                # ignored outputs produced by an earlier activity. The capture
                # above binds all executable candidate inputs; the verifier
                # itself then reads the live output through FilesystemGuard.
                return self._run_internal(
                    activity, capability.capability_id, execution_root
                )
        if capability.kind == "internal":
            return self._run_internal(activity, capability.capability_id, execution_root)
        runtime = detect_isolation_runtime()
        sandbox = str(runtime.bubblewrap)
        sandbox_project = Path("/run/upi_app_factory_project")
        bundle = tempfile.TemporaryDirectory(prefix="upi_control_plane_bundle_")
        bundle_project = Path(bundle.name) / "project"
        snapshot_identity = _materialize_repository_snapshot(
            execution_root,
            bundle_project,
            (),
        )
        if expected_identity is not None and snapshot_identity != expected_identity:
            raise ControlPlaneError("materialized candidate does not match authorized identity")
        bundle_filesystem = FilesystemGuard(bundle_project)
        try:
            for root in capability.write_roots:
                relative = root.relative_to(self.project_root).as_posix()
                bundle_filesystem.directory(relative, create=True).close()
        finally:
            bundle_filesystem.close()
        for path in sorted(bundle_project.rglob("*"), reverse=True):
            if path.is_dir():
                path.chmod(0o500)
            else:
                path.chmod(0o500 if path.stat().st_mode & stat.S_IXUSR else 0o400)
        bundle_project.chmod(0o500)
        project_fd = os.open(
            bundle_project, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        seccomp_fd = _network_seccomp_fd()
        share_network = _github_ci_share_host_network_namespace()
        isolation_argv = build_isolation_argv(share_network, seccomp_fd)
        command = [
            sandbox,
            "--die-with-parent",
            "--new-session",
            *isolation_argv,
            "--tmpfs",
            "/run",
            "--dir",
            str(sandbox_project),
            "--ro-bind", f"/proc/self/fd/{project_fd}", str(sandbox_project),
            "--proc", "/proc", "--dev", "/dev",
        ]
        runtime_paths = {
            Path("/usr"),
            Path("/lib"),
            Path("/lib64"),
            Path("/etc/alternatives"),
            runtime.python_prefix,
        }
        for runtime_path in sorted(runtime_paths, key=lambda item: (len(item.parts), str(item))):
            if runtime_path.exists() and not any(
                runtime_path != parent and runtime_path.is_relative_to(parent)
                for parent in runtime_paths
                if parent.exists()
            ):
                command.extend(("--ro-bind", str(runtime_path), str(runtime_path)))
        temporary = tempfile.TemporaryDirectory(prefix="upi_control_plane_sandbox_")
        temporary_fd = os.open(
            temporary.name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        command.extend(("--bind", f"/proc/self/fd/{temporary_fd}", "/var/tmp"))
        output_directory = tempfile.TemporaryDirectory(prefix="upi_capability_output_")
        output_root_path = Path(output_directory.name) / "roots"
        output_root_path.mkdir(mode=0o700)
        output_filesystem = FilesystemGuard(output_root_path)
        output_handles: list[DirectoryHandle] = []
        try:
            for root in capability.write_roots:
                relative = root.relative_to(self.project_root).as_posix()
                output_handle = output_filesystem.directory(relative, create=True)
                output_handles.append(output_handle)
                snapshot_filesystem = FilesystemGuard(bundle_project)
                try:
                    snapshot_handle = snapshot_filesystem.directory(relative)
                    try:
                        snapshot_filesystem.copy_tree(snapshot_handle, output_handle)
                    finally:
                        snapshot_handle.close()
                finally:
                    snapshot_filesystem.close()
                command.extend(
                    ("--bind", output_handle.proc_path, str(sandbox_project / relative))
                )
        except BaseException:
            for output_handle in output_handles:
                output_handle.close()
            output_filesystem.close()
            output_directory.cleanup()
            raise
        script_sandbox_path: Path | None = None
        if capability.script_fd is not None:
            if capability.script_relative is None:
                raise ControlPlaneError("registered script contract is incomplete")
            script_sandbox_path = sandbox_project / capability.script_relative
        staging_root: DirectoryHandle | None = None
        application_argv = build_application_argv(
            capability, self.project_root, sandbox_project, script_sandbox_path
        )
        if capability.replace_write_root:
            staging_root = output_handles[0]
            try:
                output_filesystem._remove_at(staging_root.fd, ".capability-staging")
            except FileNotFoundError:
                pass
            application_argv.extend(
                (
                    "--output-root",
                    str(
                        sandbox_project
                        / capability.write_roots[0].relative_to(self.project_root)
                        / ".capability-staging"
                    ),
                )
            )
        cwd_relative = cwd.relative_to(execution_root).as_posix()
        sandbox_cwd = sandbox_project if cwd_relative == "." else sandbox_project / cwd_relative
        command.extend(("--chdir", str(sandbox_cwd)))
        command.extend(application_argv)
        started = utc_now()
        private_script_fd = -1
        try:
            if capability.script_fd is not None:
                if script_sandbox_path is None:
                    raise ControlPlaneError("registered script contract is incomplete")
                private_script_fd = _sealed_script_fd(capability)
                command[-len(application_argv):-len(application_argv)] = (
                    "--ro-bind-data",
                    str(private_script_fd),
                    str(script_sandbox_path),
                )
            plan = ExecutionPlan(
                command=tuple(command),
                cwd=f"/proc/self/fd/{project_fd}",
                environment=env,
                pass_fds=(
                    temporary_fd,
                    project_fd,
                    seccomp_fd,
                    *(output_handle.fd for output_handle in output_handles),
                    *((private_script_fd,) if private_script_fd >= 0 else ()),
                ),
                stdin=subprocess.DEVNULL,
                close_fds=True,
                timeout_seconds=activity.timeout_seconds,
                application_argv=tuple(application_argv),
                sandbox_project=str(sandbox_project),
                output_root=application_argv[-1] if capability.replace_write_root else None,
                network_namespace=False,
                seccomp_fd=seccomp_fd,
            )
            for root, output_handle in zip(
                capability.write_roots, output_handles, strict=True
            ):
                output_handle.verify_path(
                    output_root_path / root.relative_to(self.project_root)
                )
            self.guard.verify_script(capability)
            completed = subprocess.run(
                plan.command,
                cwd=plan.cwd,
                env=plan.environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=plan.timeout_seconds,
                pass_fds=plan.pass_fds,
                stdin=plan.stdin,
                close_fds=plan.close_fds,
            )
        except BaseException:
            for output_handle in output_handles:
                output_handle.close()
            output_filesystem.close()
            output_directory.cleanup()
            raise
        finally:
            if private_script_fd >= 0:
                os.close(private_script_fd)
            os.close(temporary_fd)
            temporary.cleanup()
            os.close(project_fd)
            os.close(seccomp_fd)
            bundle.cleanup()
        finished = utc_now()
        handles: list[DirectoryHandle] = []
        private_handles: list[DirectoryHandle] = []
        publication_succeeded = False
        try:
            if completed.returncode == 0:
                # Capture output through pinned descriptors into a fresh,
                # repository-private publication tree. The sandbox never sees
                # this path, so bytes published below are exactly those copied
                # and validated after process completion.
                for root, output_handle in zip(
                    capability.write_roots, output_handles, strict=True
                ):
                    relative = root.relative_to(self.project_root).as_posix()
                    handle = self.filesystem.directory(relative, create=True)
                    handles.append(handle)
                    private_handle = self.filesystem.private_stage(
                        handle, _PRIVATE_WRITE_STAGE, copy_existing=False
                    )
                    private_handles.append(private_handle)
                    output_filesystem.copy_tree(output_handle, private_handle)
                for root, handle, private_handle in zip(
                    capability.write_roots, handles, private_handles, strict=True
                ):
                    self._promote_private_root(
                        root,
                        handle,
                        private_handle,
                        sandbox_project,
                        capability.replace_write_root,
                    )
                self.filesystem.promote_many(
                    tuple((handle, _PRIVATE_WRITE_STAGE) for handle in handles)
                )
                publication_succeeded = True
        finally:
            for private_handle in private_handles:
                private_handle.close()
            for handle in handles:
                if not publication_succeeded:
                    try:
                        self._remove_at(handle, _PRIVATE_WRITE_STAGE)
                    except (OSError, ControlPlaneError):
                        pass
                handle.close()
            for output_handle in output_handles:
                output_handle.close()
            output_filesystem.close()
            output_directory.cleanup()
        return ActivityResult(
            activity_id=activity.id,
            action=activity.action,
            kind=activity.kind,
            returncode=completed.returncode,
            stdout_sha256=sha256_text(completed.stdout),
            stderr_sha256=sha256_text(completed.stderr),
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started,
            finished_at=finished,
            authority_digests={
                key: value
                for key, value in {
                    "capability_registry_sha256": self.guard.registry_sha256,
                    "executed_script_sha256": capability.script_sha256,
                }.items()
                if value is not None
            },
        )


    def _run_internal(
        self, activity: Activity, capability_id: str, execution_root: Path
    ) -> ActivityResult:
        started = utc_now()
        stdout = ""
        stderr = ""
        returncode = 0
        filesystem = FilesystemGuard(execution_root)
        try:
            if capability_id == "self_test_create":
                filesystem.mkdir("var/control_plane_self_test")
                filesystem.write_text("var/control_plane_self_test/artifact.txt", "upi_app_factory control plane self-test\n")
            elif capability_id == "self_test_verify":
                expected = "upi_app_factory control plane self-test\n"
                actual = filesystem.read_text_optional(
                    "var/control_plane_self_test/artifact.txt"
                )
                returncode = 0 if actual == expected else 1
            elif capability_id == "self_test_cleanup":
                filesystem.remove("var/control_plane_self_test", "directory")
            elif capability_id in {"phase69_checkpoint", "phase68_70_checkpoint"}:
                import json
                content = filesystem.read_text_optional(
                    "factory_governance/phase68_70/recipient_replay_output/content_manifest.json"
                )
                try:
                    data = json.loads(content) if content is not None else {}
                except json.JSONDecodeError:
                    data = {}
                required = {"status": "PASS", "original_ignored_workspace_required": False}
                if capability_id == "phase68_70_checkpoint":
                    required = {"status": "PASS", "network_required": False, "official_certification_claimed": False}
                returncode = 0 if all(data.get(k) == v for k, v in required.items()) else 1
            else:
                raise ControlPlaneError("unknown internal capability")
        finally:
            filesystem.close()
        finished = utc_now()
        return ActivityResult(activity.id, activity.action, activity.kind, returncode,
                              sha256_text(stdout), sha256_text(stderr), stdout, stderr,
                              started, finished)

    def _remove_at(self, root: DirectoryHandle, name: str) -> None:
        root.verify_path(self.project_root / root.relative)
        try:
            self.filesystem._remove_at(root.fd, name)
        except FileNotFoundError:
            pass

    def _promote_private_root(
        self,
        registered_path: Path,
        root: DirectoryHandle,
        private_root: DirectoryHandle,
        sandbox_project: Path,
        replace_write_root: bool,
    ) -> None:
        root.verify_path(registered_path)
        private_root.verify_path(registered_path / _PRIVATE_WRITE_STAGE)
        if replace_write_root:
            # The registered replay writes its replacement beneath the already
            # private sandbox root. Collapse that inner staging tree first.
            self.filesystem.collapse_private_stage(private_root, ".capability-staging")
        if replace_write_root:
            absolute_root = str(registered_path)
            self.filesystem.replace_json_text(
                private_root,
                (
                    (f"{absolute_root}/.capability-staging", absolute_root),
                    (f"{root.relative}/.capability-staging", root.relative),
                    (
                        str(sandbox_project / root.relative / ".capability-staging"),
                        absolute_root,
                    ),
                ),
            )


def _network_seccomp_fd() -> int:
    """Return a BPF profile fd that bwrap loads after creating its namespaces."""
    library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    context = library.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise OSError("seccomp initialization failed")
    deny = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
    try:
        for name in _NETWORK_DENY_SYSCALLS:
            encoded = name.encode("ascii")
            number = library.seccomp_syscall_resolve_name(encoded)
            if number >= 0 and library.seccomp_rule_add(context, deny, number, 0) != 0:
                raise OSError(f"seccomp rule failed for {name}")
        fd = os.memfd_create("upi-network-seccomp", os.MFD_CLOEXEC)
        if library.seccomp_export_bpf(context, fd) != 0:
            os.close(fd)
            raise OSError("seccomp export failed")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    finally:
        library.seccomp_release(context)
