from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        return 0


def test_factory_start_status_repeated_start_stop_repeated_stop(tmp_path: Path) -> None:
    port = _free_port()
    if port == 0:
        assert subprocess.run(["bash", "-n", str(PROJECT_ROOT / "start_factory.sh")], cwd=PROJECT_ROOT).returncode == 0
        assert subprocess.run(["bash", "-n", str(PROJECT_ROOT / "stop_factory.sh")], cwd=PROJECT_ROOT).returncode == 0
        return
    env = {
        **os.environ,
        "UPI_APP_FACTORY_HOST": "127.0.0.1",
        "UPI_APP_FACTORY_PORT": str(port),
        "UPI_APP_FACTORY_STATE_ROOT": str(tmp_path / "state"),
        "UPI_APP_FACTORY_LOG_LEVEL": "INFO",
    }
    start = subprocess.run([str(PROJECT_ROOT / "start_factory.sh")], cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, check=False)
    try:
        assert start.returncode == 0, start.stderr + start.stdout
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    assert b'"ok"' in response.read()
                    break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        repeated = subprocess.run([str(PROJECT_ROOT / "start_factory.sh")], cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, check=False)
        assert repeated.returncode == 0
        assert "already running" in repeated.stdout
    finally:
        stop = subprocess.run([str(PROJECT_ROOT / "stop_factory.sh")], cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, check=False)
        assert stop.returncode == 0, stop.stderr + stop.stdout
    repeated_stop = subprocess.run([str(PROJECT_ROOT / "stop_factory.sh")], cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, check=False)
    assert repeated_stop.returncode == 0
    assert "not running" in repeated_stop.stdout


def test_canonical_run_factory_shell_contract_and_default_state_root() -> None:
    run_factory = PROJECT_ROOT / "run_factory.sh"
    text = run_factory.read_text(encoding="utf-8")

    assert subprocess.run(["bash", "-n", str(run_factory)], cwd=PROJECT_ROOT).returncode == 0
    assert "--no-browser" in text
    assert "--host" in text
    assert "--port" in text
    assert "--state-root" in text
    assert "--url-file" in text
    assert "requirements-recipient.txt" in text
    assert ".var/upi_app_factory" in text
    assert "/operator-ui/" in text
    assert "no OpenAI API key is required" in text
    assert "start_factory.sh" in text


def test_start_stop_scripts_share_repository_relative_state_contract() -> None:
    start_text = (PROJECT_ROOT / "start_factory.sh").read_text(encoding="utf-8")
    stop_text = (PROJECT_ROOT / "stop_factory.sh").read_text(encoding="utf-8")

    assert "${ROOT}/.var/upi_app_factory" in start_text
    assert "${ROOT}/.var/upi_app_factory" in stop_text
    assert "--state-root" in start_text
    assert "--state-root" in stop_text
    assert "runs" in start_text
    assert "portfolio" in start_text
    assert "runtime" in start_text
    assert "logs" in start_text
    assert "downloads" in start_text
    assert "evidence" in start_text
    assert "port 0" in start_text or "PORT" in start_text
