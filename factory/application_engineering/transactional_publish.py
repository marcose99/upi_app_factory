from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import shutil
import tempfile
import threading
from types import FrameType, TracebackType
from typing import Any
import uuid


class TransactionalPublishError(RuntimeError):
    """Raised when a staged directory cannot be published safely."""


class _CatchableTermination(BaseException):
    """Interrupt publication without terminating inside a rename window."""


class _SigtermDeferral(AbstractContextManager["_SigtermDeferral"]):
    """Turn a main-thread POSIX SIGTERM into rollback, then re-deliver it."""

    def __init__(self) -> None:
        self.signum: int | None = None
        self.frame: FrameType | None = None
        self.defer_only = False
        self._previous_handler: Callable[[int, FrameType | None], Any] | int | None = None
        self._enabled = False

    def __enter__(self) -> _SigtermDeferral:
        sigterm = getattr(signal, "SIGTERM", None)
        if (
            os.name == "posix"
            and sigterm is not None
            and threading.current_thread() is threading.main_thread()
        ):
            self._previous_handler = signal.getsignal(sigterm)
            if self._previous_handler == signal.SIG_IGN:
                return self
            signal.signal(sigterm, self._handle)
            self._enabled = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._enabled:
            signal.signal(signal.SIGTERM, self._previous_handler)

    def _handle(self, signum: int, frame: FrameType | None) -> None:
        self.signum = signum
        self.frame = frame
        if self._previous_handler == signal.SIG_DFL and not self.defer_only:
            raise _CatchableTermination

    def redeliver(self) -> None:
        if not self._enabled or self.signum is None:
            return
        previous_handler = self._previous_handler
        if previous_handler == signal.SIG_IGN:
            return
        if previous_handler == signal.SIG_DFL:
            os.kill(os.getpid(), self.signum)
            return
        if callable(previous_handler):
            previous_handler(self.signum, self.frame)


@dataclass(frozen=True)
class DirectoryPublication:
    candidate: Path
    destination: Path
    replace_existing: bool = True


def create_staging_directory(destination: Path) -> Path:
    """Create a private staging directory beside its eventual destination."""

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging.", dir=parent))


def cleanup_staging_directory(path: Path) -> None:
    if path.exists() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)


def publish_directories(publications: list[DirectoryPublication]) -> None:
    """Publish complete directory candidates as one rollback-capable operation.

    Every candidate must be a sibling of its destination so each rename stays on
    one filesystem. Existing destinations are first renamed to private backups;
    any failure restores every prior destination before the exception escapes.
    On a POSIX main thread, SIGTERM is converted to rollback and re-delivered
    only after destinations are stable. Other environments retain exception
    rollback but do not add a process-termination guarantee.
    """

    if not publications:
        return

    resolved_destinations = [item.destination.resolve() for item in publications]
    if len(set(resolved_destinations)) != len(resolved_destinations):
        raise TransactionalPublishError("publication destinations must be unique")
    for index, left in enumerate(resolved_destinations):
        for right in resolved_destinations[index + 1 :]:
            if left in right.parents or right in left.parents:
                raise TransactionalPublishError("publication destinations must not overlap")

    for item in publications:
        candidate = item.candidate
        destination = item.destination
        if not candidate.is_dir() or candidate.is_symlink():
            raise TransactionalPublishError(f"staged directory is invalid: {candidate}")
        if candidate.parent.resolve() != destination.parent.resolve():
            raise TransactionalPublishError(
                f"staged directory must be beside its destination: {candidate}"
            )
        if destination.is_symlink():
            raise TransactionalPublishError(f"refusing to replace symlink: {destination}")
        if destination.exists() and not destination.is_dir():
            raise TransactionalPublishError(f"publication destination is not a directory: {destination}")
        if destination.exists() and not item.replace_existing:
            raise TransactionalPublishError(f"destination already exists: {destination}")

    backups: dict[Path, Path] = {}
    published: list[DirectoryPublication] = []
    failure: BaseException | None = None
    failure_traceback: TracebackType | None = None
    rollback_errors: list[str] = []
    sigterm = _SigtermDeferral()
    with sigterm:
        try:
            for item in publications:
                candidate = item.candidate
                destination = item.destination
                if destination.exists():
                    backup = destination.parent / f".{destination.name}.backup.{uuid.uuid4().hex}"
                    backups[destination] = backup
                    destination.replace(backup)
                published.append(item)
                candidate.replace(destination)
        except BaseException as exc:
            failure = exc
            failure_traceback = exc.__traceback__
            sigterm.defer_only = True
            for item in reversed(publications):
                destination = item.destination
                prior_destination = backups.get(destination)
                try:
                    if item in published and destination.exists():
                        if item.candidate.exists():
                            cleanup_staging_directory(item.candidate)
                        destination.replace(item.candidate)
                    if prior_destination is not None and prior_destination.exists():
                        prior_destination.replace(destination)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{destination}: {rollback_exc}")
        else:
            sigterm.defer_only = True
            for backup in backups.values():
                cleanup_staging_directory(backup)

    if rollback_errors:
        raise TransactionalPublishError(
            "publication failed and rollback was incomplete: " + "; ".join(rollback_errors)
        ) from failure
    sigterm.redeliver()
    if failure is not None and not isinstance(failure, _CatchableTermination):
        raise failure.with_traceback(failure_traceback)
