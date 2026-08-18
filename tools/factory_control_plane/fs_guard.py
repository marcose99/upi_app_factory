from __future__ import annotations

import os
import stat
import secrets
import ctypes
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.factory_control_plane.common import ControlPlaneError


_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
_RENAME_NOREPLACE = 1
_RENAME_EXCHANGE = 2


def _rename_noreplace(source: str, destination: str, source_fd: int, destination_fd: int) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = library.renameat2
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(
        source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), _RENAME_NOREPLACE
    ) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def _rename_exchange(source: str, destination: str, parent_fd: int) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = library.renameat2
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(
        parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), _RENAME_EXCHANGE
    ) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def _parts(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in {"", ".", ".."} for p in path.parts):
        raise ControlPlaneError("filesystem path is not a safe repository-relative path")
    return path.parts


@dataclass
class DirectoryHandle:
    fd: int
    relative: str

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> DirectoryHandle:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def proc_path(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    def verify_path(self, path: Path) -> None:
        try:
            opened = os.fstat(self.fd)
            current = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise ControlPlaneError("filesystem identity drifted before effect") from exc
        if not stat.S_ISDIR(current.st_mode) or (opened.st_dev, opened.st_ino) != (
            current.st_dev,
            current.st_ino,
        ):
            raise ControlPlaneError("filesystem identity drifted before effect")


class FilesystemGuard:
    """Linux descriptor-relative filesystem effects beneath one pinned root."""

    def __init__(self, root: Path) -> None:
        try:
            self._root_fd = os.open(root, _DIR_FLAGS)
        except OSError as exc:
            raise ControlPlaneError("repository root identity is unavailable") from exc
        self.root = root.resolve()

    def close(self) -> None:
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def root_handle(self) -> DirectoryHandle:
        return DirectoryHandle(os.dup(self._root_fd), ".")

    def _walk(self, parts: tuple[str, ...], create: bool = False) -> int:
        fd = os.dup(self._root_fd)
        try:
            for part in parts:
                try:
                    next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return fd
        except FileNotFoundError:
            os.close(fd)
            raise
        except OSError as exc:
            os.close(fd)
            raise ControlPlaneError("filesystem identity changed or path is unsafe") from exc

    def directory(self, relative: str, create: bool = False) -> DirectoryHandle:
        parts = _parts(relative)
        return DirectoryHandle(self._walk(parts, create), PurePosixPath(*parts).as_posix())

    def parent(self, relative: str, create: bool = False) -> tuple[DirectoryHandle, str]:
        parts = _parts(relative)
        parent_parts = parts[:-1]
        fd = self._walk(parent_parts, create) if parent_parts else os.dup(self._root_fd)
        return DirectoryHandle(fd, PurePosixPath(*parent_parts).as_posix()), parts[-1]

    def mkdir(self, relative: str) -> None:
        parent, name = self.parent(relative, create=True)
        with parent:
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent.fd)
            except FileExistsError:
                fd = os.open(name, _DIR_FLAGS, dir_fd=parent.fd)
                os.close(fd)
            except OSError as exc:
                raise ControlPlaneError("safe directory creation denied") from exc

    def write_text(self, relative: str, payload: str) -> None:
        parent, name = self.parent(relative, create=True)
        with parent:
            try:
                self._publish_bytes(parent.fd, name, payload.encode("utf-8"))
            except OSError as exc:
                raise ControlPlaneError("safe file write denied") from exc

    def _publish_bytes(self, parent_fd: int, name: str, payload: bytes) -> None:
        """Publish a completed private inode; never mutate a pathname-owned inode."""
        temporary = f".capability-new-{secrets.token_hex(16)}"
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        prior_fd = -1
        prior_name = f".capability-prior-{secrets.token_hex(16)}"
        try:
            remaining = memoryview(payload)
            while remaining:
                remaining = remaining[os.write(fd, remaining) :]
            os.fsync(fd)
            opened = os.fstat(fd)
            self._verify_entry(parent_fd, temporary, opened)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise ControlPlaneError("safe file publication denied")
            # Quarantine the old entry before publication. NOREPLACE makes a
            # substitution after quarantine fail rather than unlinking it.
            try:
                prior_fd = os.open(
                    name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd
                )
            except FileNotFoundError:
                pass
            else:
                prior = os.fstat(prior_fd)
                if not stat.S_ISREG(prior.st_mode):
                    raise ControlPlaneError("safe file replacement denied")
                os.rename(name, prior_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                self._verify_entry(parent_fd, prior_name, prior)
            _rename_noreplace(temporary, name, parent_fd, parent_fd)
            if prior_fd >= 0:
                os.unlink(prior_name, dir_fd=parent_fd)
        finally:
            os.close(fd)
            if prior_fd >= 0:
                os.close(prior_fd)
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            try:
                _rename_noreplace(prior_name, name, parent_fd, parent_fd)
            except FileNotFoundError:
                pass
            except FileExistsError:
                pass

    def read_text(self, relative: str) -> str:
        parent, name = self.parent(relative)
        with parent:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent.fd)
                with os.fdopen(fd, encoding="utf-8") as stream:
                    return stream.read()
            except OSError as exc:
                raise ControlPlaneError("safe file read denied") from exc

    def read_text_optional(self, relative: str) -> str | None:
        """Read a regular file, returning ``None`` only when its path is absent."""
        try:
            parent, name = self.parent(relative)
        except FileNotFoundError:
            return None
        with parent:
            try:
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=parent.fd,
                )
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise ControlPlaneError("safe file read denied") from exc
            try:
                with os.fdopen(fd, encoding="utf-8") as stream:
                    return stream.read()
            except OSError as exc:
                raise ControlPlaneError("safe file read denied") from exc

    def kind(self, relative: str) -> str | None:
        try:
            parent, name = self.parent(relative)
        except FileNotFoundError:
            return None
        with parent:
            try:
                mode = os.stat(name, dir_fd=parent.fd, follow_symlinks=False).st_mode
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise ControlPlaneError("safe path inspection denied") from exc
        if stat.S_ISDIR(mode):
            return "directory"
        if stat.S_ISREG(mode):
            return "file"
        return "other"

    def remove(self, relative: str, expected_kind: str | None = None) -> bool:
        # Reconciliation is intentionally idempotent: if any parent component
        # is already absent, the requested object cannot exist and there is
        # nothing to remove. Existing objects still traverse the descriptor-
        # relative identity/kind/hard-link checks below.
        try:
            parent, name = self.parent(relative)
        except FileNotFoundError:
            return False
        with parent:
            try:
                object_fd = os.open(
                    name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent.fd
                )
            except FileNotFoundError:
                return False
            try:
                opened = os.fstat(object_fd)
                kind = self._safe_kind(opened)
                if expected_kind is not None and kind != expected_kind:
                    raise ControlPlaneError("filesystem object kind mismatch")
                self._quarantine_and_remove(parent.fd, name, object_fd, opened, kind)
            except OSError as exc:
                raise ControlPlaneError("safe recursive removal denied") from exc
            finally:
                os.close(object_fd)
            return True

    def _empty_directory(self, fd: int) -> None:
        for name in os.listdir(fd):
            child = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
            try:
                opened = os.fstat(child)
                kind = self._safe_kind(opened)
                self._quarantine_and_remove(fd, name, child, opened, kind)
            finally:
                os.close(child)

    @staticmethod
    def _stable_copy_metadata(value: os.stat_result) -> tuple[int, ...]:
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

    def private_stage(
        self, root: DirectoryHandle, staging_name: str, *, copy_existing: bool = True
    ) -> DirectoryHandle:
        """Create an isolated writable copy without exposing host-root inodes."""
        root.verify_path(self.root / root.relative)
        try:
            stale_fd = os.open(staging_name, _DIR_FLAGS, dir_fd=root.fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ControlPlaneError("private writable staging cleanup denied") from exc
        else:
            try:
                self._validate_tree_fd(stale_fd)
            finally:
                os.close(stale_fd)
            try:
                self._remove_at(root.fd, staging_name)
            except (OSError, ControlPlaneError) as exc:
                raise ControlPlaneError("private writable staging cleanup denied") from exc
        staging_fd = -1
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=root.fd)
            staging_fd = os.open(staging_name, _DIR_FLAGS, dir_fd=root.fd)
            if copy_existing:
                self._copy_private_tree(root.fd, staging_fd, staging_name)
            root.verify_path(self.root / root.relative)
            return DirectoryHandle(
                staging_fd, PurePosixPath(root.relative, staging_name).as_posix()
            )
        except (OSError, ControlPlaneError) as exc:
            if staging_fd >= 0:
                os.close(staging_fd)
            try:
                self._remove_at(root.fd, staging_name)
            except (FileNotFoundError, OSError, ControlPlaneError):
                pass
            raise ControlPlaneError("private writable staging denied") from exc

    def copy_tree(self, source: DirectoryHandle, destination: DirectoryHandle) -> None:
        """Copy a validated captured tree into an empty private staging root."""
        self._copy_private_tree(source.fd, destination.fd)

    def _copy_private_tree(
        self, source_fd: int, destination_fd: int, skip_name: str | None = None
    ) -> None:
        for name in sorted(os.listdir(source_fd)):
            if skip_name is not None and name == skip_name:
                continue
            inspect_fd = -1
            child_fd = -1
            destination_child_fd = -1
            try:
                inspect_fd = os.open(
                    name, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=source_fd
                )
                inspected = os.fstat(inspect_fd)
                kind = self._safe_kind(inspected)
                self._verify_entry(source_fd, name, inspected)
                if kind == "directory":
                    child_fd = os.open(name, _DIR_FLAGS, dir_fd=source_fd)
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (inspected.st_dev, inspected.st_ino):
                        raise ControlPlaneError("writable-root directory identity drifted")
                    os.mkdir(name, mode=0o700, dir_fd=destination_fd)
                    destination_child_fd = os.open(name, _DIR_FLAGS, dir_fd=destination_fd)
                    self._copy_private_tree(child_fd, destination_child_fd)
                    self._verify_entry(source_fd, name, inspected)
                else:
                    child_fd = os.open(
                        name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=source_fd
                    )
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (inspected.st_dev, inspected.st_ino):
                        raise ControlPlaneError("writable-root file identity drifted")
                    destination_child_fd = os.open(
                        name,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_CLOEXEC
                        | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=destination_fd,
                    )
                    while data := os.read(child_fd, 1024 * 1024):
                        view = memoryview(data)
                        while view:
                            written = os.write(destination_child_fd, view)
                            if written <= 0:
                                raise ControlPlaneError("private writable copy did not progress")
                            view = view[written:]
                    os.fsync(destination_child_fd)
                    after = os.fstat(child_fd)
                    self._verify_entry(source_fd, name, inspected)
                    if self._stable_copy_metadata(opened) != self._stable_copy_metadata(after):
                        raise ControlPlaneError("writable-root source mutated during private copy")
                    copied = os.fstat(destination_child_fd)
                    if not stat.S_ISREG(copied.st_mode) or copied.st_nlink != 1:
                        raise ControlPlaneError("private writable copy identity is unsafe")
            finally:
                if destination_child_fd >= 0:
                    os.close(destination_child_fd)
                if child_fd >= 0:
                    os.close(child_fd)
                if inspect_fd >= 0:
                    os.close(inspect_fd)

    def _validate_tree_fd(self, directory_fd: int, skip_name: str | None = None) -> None:
        for name in sorted(os.listdir(directory_fd)):
            if skip_name is not None and name == skip_name:
                continue
            inspect_fd = os.open(
                name, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            child_fd = -1
            try:
                opened = os.fstat(inspect_fd)
                kind = self._safe_kind(opened)
                self._verify_entry(directory_fd, name, opened)
                if kind == "directory":
                    child_fd = os.open(name, _DIR_FLAGS, dir_fd=directory_fd)
                    current = os.fstat(child_fd)
                    if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                        raise ControlPlaneError("filesystem identity drifted before traversal")
                    self._validate_tree_fd(child_fd)
                    self._verify_entry(directory_fd, name, opened)
            finally:
                if child_fd >= 0:
                    os.close(child_fd)
                os.close(inspect_fd)

    def clear_except(self, directory: DirectoryHandle, keep: str) -> None:
        for name in os.listdir(directory.fd):
            if name != keep:
                self._remove_at(directory.fd, name)

    def _remove_at(self, parent_fd: int, name: str) -> None:
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            kind = self._safe_kind(opened)
            self._quarantine_and_remove(parent_fd, name, fd, opened, kind)
        finally:
            os.close(fd)

    def _quarantine_and_remove(
        self, parent_fd: int, name: str, fd: int, opened: os.stat_result, kind: str
    ) -> None:
        quarantine = f".capability-remove-{secrets.token_hex(16)}"
        os.rename(name, quarantine, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        try:
            self._verify_entry(parent_fd, quarantine, opened)
            if kind == "directory":
                self._empty_directory(fd)
                self._verify_entry(parent_fd, quarantine, opened)
                os.rmdir(quarantine, dir_fd=parent_fd)
            else:
                os.unlink(quarantine, dir_fd=parent_fd)
        except BaseException:
            # Restore only when the original name is still vacant. The verified
            # quarantine name remains bound to the retained descriptor.
            try:
                os.rename(quarantine, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except OSError:
                pass
            raise

    @staticmethod
    def _safe_kind(opened: os.stat_result) -> str:
        if stat.S_ISDIR(opened.st_mode):
            if opened.st_nlink < 2:
                raise ControlPlaneError("unsafe filesystem object identity")
            return "directory"
        if stat.S_ISREG(opened.st_mode):
            if opened.st_nlink != 1:
                raise ControlPlaneError("unsafe hard-linked file")
            return "file"
        raise ControlPlaneError("unsafe filesystem object type")

    @staticmethod
    def _verify_entry(parent_fd: int, name: str, opened: os.stat_result) -> None:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino, stat.S_IFMT(current.st_mode)) != (
            opened.st_dev,
            opened.st_ino,
            stat.S_IFMT(opened.st_mode),
        ):
            raise ControlPlaneError("filesystem identity drifted before effect")

    def promote(self, root: DirectoryHandle, staging_name: str) -> None:
        self.promote_many(((root, staging_name),))

    def promote_many(self, publications: tuple[tuple[DirectoryHandle, str], ...]) -> None:
        prepared: list[tuple[DirectoryHandle, str, str]] = []
        exchanged: list[tuple[DirectoryHandle, str, str]] = []
        try:
            for root, staging_name in publications:
                staging_fd = os.open(staging_name, _DIR_FLAGS, dir_fd=root.fd)
                try:
                    self._validate_tree_fd(staging_fd)
                    self._validate_tree_fd(root.fd, staging_name)
                finally:
                    os.close(staging_fd)
                if root.relative == ".":
                    raise ControlPlaneError("repository root cannot be atomically replaced")
                parent, root_name = self.parent(root.relative)
                sibling = f".capability-publish-{secrets.token_hex(16)}"
                os.rename(staging_name, sibling, src_dir_fd=root.fd, dst_dir_fd=parent.fd)
                prepared.append((parent, root_name, sibling))
            for item in prepared:
                parent, root_name, sibling = item
                _rename_exchange(sibling, root_name, parent.fd)
                exchanged.append(item)
            # Old trees are no longer reachable by their registered names.
            # Cleanup is best-effort and cannot invalidate publication.
            for parent, _root_name, sibling in prepared:
                try:
                    self._remove_at(parent.fd, sibling)
                except (OSError, ControlPlaneError):
                    pass
        except (OSError, ControlPlaneError) as exc:
            for parent, root_name, sibling in reversed(exchanged):
                try:
                    _rename_exchange(sibling, root_name, parent.fd)
                except OSError as rollback_exc:
                    raise ControlPlaneError("staged promotion rollback failed") from rollback_exc
            raise ControlPlaneError("safe staged promotion denied") from exc
        finally:
            for parent, _root_name, _sibling in prepared:
                parent.close()

    def collapse_private_stage(self, root: DirectoryHandle, staging_name: str) -> None:
        """Collapse a nested stage that is not yet visible outside the sandbox."""
        staging_fd = os.open(staging_name, _DIR_FLAGS, dir_fd=root.fd)
        try:
            self._validate_tree_fd(staging_fd)
            self.clear_except(root, staging_name)
            for name in sorted(os.listdir(staging_fd)):
                os.rename(name, name, src_dir_fd=staging_fd, dst_dir_fd=root.fd)
            os.rmdir(staging_name, dir_fd=root.fd)
        except OSError as exc:
            raise ControlPlaneError("private staged collapse denied") from exc
        finally:
            os.close(staging_fd)

    def replace_json_text(
        self, root: DirectoryHandle, replacements: tuple[tuple[str, str], ...]
    ) -> None:
        self._replace_json_at(root.fd, replacements)

    def _replace_json_at(self, directory_fd: int, replacements: tuple[tuple[str, str], ...]) -> None:
        for name in os.listdir(directory_fd):
            mode = os.stat(name, dir_fd=directory_fd, follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                child = os.open(name, _DIR_FLAGS, dir_fd=directory_fd)
                try:
                    self._replace_json_at(child, replacements)
                finally:
                    os.close(child)
            elif stat.S_ISREG(mode) and name.endswith(".json"):
                try:
                    fd = os.open(
                        name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd
                    )
                    try:
                        opened = os.fstat(fd)
                        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                            raise ControlPlaneError("unsafe staged JSON identity")
                        payload = os.read(fd, opened.st_size).decode("utf-8")
                        normalized = payload
                        for old, new in replacements:
                            normalized = normalized.replace(old, new)
                        if normalized != payload:
                            self._publish_bytes(directory_fd, name, normalized.encode("utf-8"))
                    finally:
                        os.close(fd)
                except (OSError, UnicodeError) as exc:
                    raise ControlPlaneError("safe staged JSON normalization denied") from exc
