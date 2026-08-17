from __future__ import annotations

from pathlib import Path

import pytest

from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.host_runtime import (
    detect_isolation_runtime,
    resolve_python_runtime,
)


def test_declared_linux_isolation_runtime_is_available() -> None:
    runtime = detect_isolation_runtime()

    assert runtime.bubblewrap.is_absolute()
    assert runtime.python == resolve_python_runtime()
    assert runtime.python.is_file()
    assert runtime.python_prefix.is_dir()


def test_unsupported_host_detection_fails_closed_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tools.factory_control_plane.host_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("tools.factory_control_plane.host_runtime.Path.is_dir", lambda _path: False)
    monkeypatch.setattr("tools.factory_control_plane.host_runtime.shutil.which", lambda _name: None)

    with pytest.raises(ControlPlaneError) as raised:
        detect_isolation_runtime()

    message = str(raised.value)
    assert message.startswith("capability isolation runtime is unsupported; missing: ")
    assert "bubblewrap" in message
    assert "linux" in message
    assert "procfs" in message


def test_python_runtime_resolution_is_not_layout_specific() -> None:
    runtime = resolve_python_runtime()

    assert runtime.is_absolute()
    assert runtime != Path("/usr/bin/python3") or runtime.is_file()
