from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.factory_control_plane.common import ControlPlaneError


@dataclass(frozen=True)
class IsolationRuntime:
    """Validated host facilities required by the Linux capability sandbox."""

    bubblewrap: Path
    python: Path
    python_prefix: Path


def resolve_python_runtime() -> Path:
    """Resolve the current Python installation without assuming a filesystem layout."""
    candidate = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ControlPlaneError("Python capability runtime is unavailable")
    return candidate


def detect_isolation_runtime() -> IsolationRuntime:
    """Fail closed with one stable error when the declared Linux sandbox is unavailable."""
    missing: list[str] = []
    if platform.system() != "Linux":
        missing.append("linux")
    if not Path("/proc/self/fd").is_dir():
        missing.append("procfs")
    if not hasattr(os, "memfd_create"):
        missing.append("memfd")
    try:
        libc = ctypes.CDLL(None)
        getattr(libc, "renameat2")
    except (OSError, AttributeError):
        missing.append("renameat2")
    try:
        ctypes.CDLL("libseccomp.so.2")
    except OSError:
        missing.append("libseccomp")
    bubblewrap_value = shutil.which("bwrap")
    if bubblewrap_value is None:
        missing.append("bubblewrap")
        bubblewrap = Path("bwrap")
    else:
        bubblewrap = Path(bubblewrap_value).resolve()
        if not bubblewrap.is_file() or not os.access(bubblewrap, os.X_OK):
            missing.append("bubblewrap")
    try:
        python = resolve_python_runtime()
    except ControlPlaneError:
        missing.append("python")
        python = Path(sys.executable)
    if missing:
        raise ControlPlaneError(
            "capability isolation runtime is unsupported; missing: " + ", ".join(sorted(set(missing)))
        )
    python_prefix = Path(sys.base_prefix).resolve()
    if not python_prefix.is_dir():
        raise ControlPlaneError("Python capability runtime prefix is unavailable")
    return IsolationRuntime(
        bubblewrap=bubblewrap,
        python=python,
        python_prefix=python_prefix,
    )
