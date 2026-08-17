from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from tools.factory_control_plane.common import (
    ControlPlaneError,
    resolve_under_root,
    sha256_bytes,
)
from tools.factory_control_plane.manifest import Activity
from tools.factory_control_plane.host_runtime import resolve_python_runtime


PROHIBITED_ENVIRONMENT_FRAGMENTS = (
    "TOKEN", "SECRET", "PASSWORD", "KEY", "PROXY", "PATH", "HOME", "SHELL",
    "PYTHON", "LD_", "DYLD_", "GIT_", "SSH_", "SSL", "CERT", "AUTH",
)
PROTECTED_REPOSITORY_ROOTS = frozenset(
    {
        ".git", ".github", "config", "docs", "factory", "scripts", "src",
        "tests", "tools", "AGENTS.md",
    }
)


def _resolve_unprotected_write_root(project_root: Path, value: str) -> Path:
    lexical_first = Path(value).parts[0] if Path(value).parts else "."
    if lexical_first in PROTECTED_REPOSITORY_ROOTS:
        raise ControlPlaneError(
            "automatic capability write root targets protected repository content"
        )
    target = resolve_under_root(project_root, value)
    relative = target.relative_to(project_root)
    first = relative.parts[0] if relative.parts else "."
    if target == project_root or first in PROTECTED_REPOSITORY_ROOTS:
        raise ControlPlaneError(
            "automatic capability write root targets protected repository content"
        )
    return target


@dataclass(frozen=True)
class ResolvedCapability:
    capability_id: str
    kind: str
    executable: Path | None
    arguments: tuple[str, ...]
    write_roots: tuple[Path, ...]
    network: bool
    replace_write_root: bool
    script_fd: int | None = None
    script_relative: str | None = None
    script_sha256: str | None = None
    script_identity: tuple[int, int] | None = None


class CapabilityGuard:
    """Resolve manifest requests to immutable, repository-owned capabilities."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        path = self.project_root / "config/control_plane/automatic_capabilities.json"
        self.disposable_roots: tuple[Path, ...] = ()
        self.capabilities: dict[tuple[str, ...], ResolvedCapability] = {}
        self.registry_sha256: str | None = None
        self._closed = False
        if not path.exists():
            return
        try:
            registry_bytes = path.read_bytes()
            raw = json.loads(registry_bytes)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ControlPlaneError("automatic capability registry is unreadable") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 2:
            raise ControlPlaneError("automatic capability registry schema is not frozen v2")
        self.registry_sha256 = sha256_bytes(registry_bytes)
        self.disposable_roots = tuple(
            _resolve_unprotected_write_root(self.project_root, value)
            for value in raw.get("disposable_roots", [])
            if isinstance(value, str)
        )
        for item in raw.get("capabilities", []):
            self._register(item)
        if not self.capabilities:
            raise ControlPlaneError("automatic capability registry is empty")

    def close(self) -> None:
        if self._closed:
            return
        for capability in self.capabilities.values():
            if capability.script_fd is not None:
                try:
                    os.close(capability.script_fd)
                except OSError:
                    pass
        self._closed = True

    def _register(self, item: object) -> None:
        if not isinstance(item, dict) or set(item) != {
            "id", "request_argv", "kind", "executable", "script", "script_sha256",
            "arguments", "effects", "write_roots", "environment", "network",
            "replace_write_root",
        }:
            raise ControlPlaneError("automatic capability entry does not match frozen contract")
        request = item["request_argv"]
        arguments = item["arguments"]
        roots = item["write_roots"]
        effects = item["effects"]
        if not all(isinstance(value, list) for value in (request, arguments, roots, effects)):
            raise ControlPlaneError("automatic capability lists are malformed")
        if not request or not all(isinstance(v, str) and v for v in request):
            raise ControlPlaneError("automatic capability request is malformed")
        if not all(isinstance(v, str) for v in arguments + roots + effects):
            raise ControlPlaneError("automatic capability contract is malformed")
        if item["environment"] != [] or item["network"] is not False:
            raise ControlPlaneError("automatic capabilities must have empty environment and no network")
        replace_write_root = item["replace_write_root"]
        if not isinstance(replace_write_root, bool):
            raise ControlPlaneError("automatic capability replacement mode is malformed")
        if replace_write_root and (effects != ["write"] or len(roots) != 1):
            raise ControlPlaneError("replacement mode requires one write-only registered root")
        kind = item["kind"]
        executable: Path | None = None
        resolved_arguments = tuple(arguments)
        script_fd: int | None = None
        script_relative: str | None = None
        script_sha256: str | None = None
        script_identity: tuple[int, int] | None = None
        if kind == "python_script":
            if item["executable"] != "python3" or not isinstance(item["script"], str):
                raise ControlPlaneError("Python capability executable identity is not canonical")
            executable = resolve_python_runtime()
            digest = item["script_sha256"]
            if not isinstance(digest, str):
                raise ControlPlaneError("registered script identity does not match its digest")
            script_relative = item["script"]
            script_fd = self._open_script(script_relative)
            opened = os.fstat(script_fd)
            actual_digest = self._descriptor_digest(script_fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or actual_digest != digest
            ):
                os.close(script_fd)
                raise ControlPlaneError("registered script identity does not match its digest")
            script_sha256 = digest
            script_identity = (opened.st_dev, opened.st_ino)
        elif kind == "internal":
            if item["executable"] is not None or item["script"] is not None or item["script_sha256"] is not None:
                raise ControlPlaneError("internal capability must not name an executable")
        else:
            raise ControlPlaneError("unknown automatic capability kind")
        capability = ResolvedCapability(
            capability_id=str(item["id"]), kind=str(kind), executable=executable,
            arguments=resolved_arguments,
            write_roots=tuple(
                _resolve_unprotected_write_root(self.project_root, value)
                for value in roots
            ),
            network=False,
            replace_write_root=replace_write_root,
            script_fd=script_fd,
            script_relative=script_relative,
            script_sha256=script_sha256,
            script_identity=script_identity,
        )
        key = tuple(request)
        if key in self.capabilities:
            if script_fd is not None:
                os.close(script_fd)
            raise ControlPlaneError("duplicate automatic capability request")
        self.capabilities[key] = capability

    def _open_script(self, relative: str) -> int:
        path = Path(relative)
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise ControlPlaneError("registered script path is unsafe")
        parent_fd = -1
        try:
            parent_fd = os.open(
                self.project_root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            for part in path.parts[:-1]:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
                os.close(parent_fd)
                parent_fd = next_fd
            return os.open(
                path.parts[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise ControlPlaneError("registered script identity is unavailable") from exc
        finally:
            if parent_fd >= 0:
                os.close(parent_fd)

    @staticmethod
    def _descriptor_digest(fd: int) -> str:
        digest = hashlib.sha256()
        os.lseek(fd, 0, os.SEEK_SET)
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        os.lseek(fd, 0, os.SEEK_SET)
        return digest.hexdigest()

    def verify_script(self, capability: ResolvedCapability) -> None:
        if capability.kind != "python_script" or capability.script_fd is None:
            return
        try:
            opened = os.fstat(capability.script_fd)
            identity = (opened.st_dev, opened.st_ino)
            digest = self._descriptor_digest(capability.script_fd)
        except OSError as exc:
            raise ControlPlaneError("registered script identity drifted before execution") from exc
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or identity != capability.script_identity
            or digest != capability.script_sha256
        ):
            raise ControlPlaneError("registered script identity drifted before execution")

    def resolve(self, activity: Activity) -> ResolvedCapability:
        if activity.environment_allowlist:
            raise ControlPlaneError("automatic capabilities may not inherit environment variables")
        capability = self.capabilities.get(activity.argv)
        if capability is None:
            raise ControlPlaneError("command is not an exact registered capability")
        declared = tuple(resolve_under_root(self.project_root, p) for p in activity.allowed_write_paths)
        if set(declared) != set(capability.write_roots):
            raise ControlPlaneError("registered capability write contract does not match manifest")
        return capability

    def validate_runtime_noise(self, path_text: str, allowed_scope: tuple[str, ...]) -> Path:
        lexical_first = Path(path_text).parts[0] if Path(path_text).parts else "."
        if lexical_first in PROTECTED_REPOSITORY_ROOTS:
            raise ControlPlaneError("runtime noise targets protected repository content")
        target = resolve_under_root(self.project_root, path_text)
        scope = tuple(resolve_under_root(self.project_root, value) for value in allowed_scope)
        if not scope or not any(target == root or target.is_relative_to(root) for root in scope):
            raise ControlPlaneError("runtime noise is outside enforced campaign write scope")
        if not any(target == root or target.is_relative_to(root) for root in self.disposable_roots):
            raise ControlPlaneError("runtime noise is not within a registered disposable root")
        relative = target.relative_to(self.project_root)
        first = relative.parts[0] if relative.parts else "."
        if first in PROTECTED_REPOSITORY_ROOTS or target == self.project_root:
            raise ControlPlaneError("runtime noise targets protected repository content")
        return target


def sanitized_environment(allowed_names: tuple[str, ...]) -> dict[str, str]:
    if allowed_names:
        raise ControlPlaneError("automatic environment inheritance is prohibited")
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "TMPDIR": "/var/tmp",
    }
