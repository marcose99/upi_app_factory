from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from typing import Any
from urllib import request as urllib_request
from urllib.error import URLError

from factory.operator_portal.runtime_contracts import ProcessIdentity, RuntimeContractError, RuntimeState, RuntimeStatus
from factory.operator_portal.runtime_store import RuntimeStore, default_binding


class RuntimeSupervisor:
    def __init__(self, *, project_root: Path, store: RuntimeStore | None = None) -> None:
        self.project_root = project_root.resolve()
        self.store = store or RuntimeStore(project_root=self.project_root)

    def binding(self, *, run_id: str, port: int = 18042) -> Any:
        return default_binding(self.project_root, run_id=run_id, port=port)

    def status(self, *, run_id: str, port: int = 18042) -> RuntimeStatus:
        binding = self.binding(run_id=run_id, port=port)
        status = self.store.read_status(run_id, binding)
        if status.process and not self._process_matches(status.process):
            try:
                return self.store.transition_status(status, RuntimeState.STALE, health={"status": "stale_process_identity"})
            except RuntimeContractError:
                return RuntimeStatus(
                    state=RuntimeState.STALE,
                    binding=binding,
                    process=status.process,
                    health={"status": "stale_process_identity"},
                    updated_at_utc=status.updated_at_utc,
                )
        if status.state == RuntimeState.READY:
            health = self._health(binding)
            if health.get("status") != "ok":
                return self.store.transition_status(status, RuntimeState.DEGRADED, health=health)
        return status

    def start(self, *, run_id: str, port: int = 18042, readiness_timeout: float = 10.0) -> RuntimeStatus:
        binding = self.binding(run_id=run_id, port=port)
        current = self.status(run_id=run_id, port=port)
        if current.state == RuntimeState.READY:
            return current
        if self._port_in_use(port):
            if current.process and self._process_matches(current.process):
                return current
            self.store.append_event(run_id, "runtime_start_rejected", {"reason": "port_collision", "port": port})
            raise RuntimeContractError("owned runtime port is already in use")

        app_root = Path(binding.application_root)
        if not (app_root / "app/upi_dispute_app/main.py").is_file():
            raise RuntimeContractError("generated application entrypoint is missing")

        starting = self.store.transition_status(current, RuntimeState.STARTING, health={"status": "starting"})
        data_dir = self.store.data_dir(run_id)
        data_dir.mkdir(parents=True, exist_ok=True)
        log_handle = self.store.log_path(run_id).open("ab")
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": f"{app_root / 'app'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep),
                "UPI_DISPUTE_APP_ENV": "local",
                "UPI_DISPUTE_DATA_DIR": data_dir.as_posix(),
                "UPI_DISPUTE_SQLITE_PATH": (data_dir / "disputes.sqlite3").as_posix(),
                "UPI_DISPUTE_AUDIT_LOG_PATH": (data_dir / "audit_events.jsonl").as_posix(),
                "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE": "mock",
                "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS": "false",
                "UPI_DISPUTE_ALLOW_REAL_SECRETS": "false",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", binding.entrypoint, "--host", binding.host, "--port", str(binding.port)],
            cwd=app_root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
        process = ProcessIdentity(
            pid=proc.pid,
            process_start_time=self._process_start_time(proc.pid),
            executable=sys.executable,
        )
        self.store.write_status(RuntimeStatus(state=RuntimeState.STARTING, binding=binding, process=process, health={"status": "starting"}, updated_at_utc=starting.updated_at_utc))
        deadline = time.monotonic() + readiness_timeout
        last_health: dict[str, Any] = {"status": "starting"}
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                failed = self.store.read_status(run_id, binding)
                return self.store.transition_status(failed, RuntimeState.FAILED, process=process, health={"status": "process_exited", "returncode": proc.returncode})
            last_health = self._health(binding)
            if last_health.get("status") == "ok":
                ready = self.store.read_status(run_id, binding)
                return self.store.transition_status(ready, RuntimeState.READY, process=process, health=last_health)
            time.sleep(0.1)
        self.stop(run_id=run_id, port=port, timeout=2.0)
        raise RuntimeContractError(f"runtime readiness timed out after {readiness_timeout:.1f}s")

    def restart(self, *, run_id: str, port: int = 18042) -> RuntimeStatus:
        self.stop(run_id=run_id, port=port)
        return self.start(run_id=run_id, port=port)

    def stop(self, *, run_id: str, port: int = 18042, timeout: float = 5.0) -> RuntimeStatus:
        binding = self.binding(run_id=run_id, port=port)
        current = self.status(run_id=run_id, port=port)
        if current.state in {RuntimeState.ABSENT, RuntimeState.STOPPED, RuntimeState.STALE}:
            stopped = RuntimeStatus(state=RuntimeState.STOPPED, binding=binding, process=None, health={"status": "stopped"}, updated_at_utc=current.updated_at_utc)
            self.store.write_status(stopped)
            return stopped
        stopping = self.store.transition_status(current, RuntimeState.STOPPING, health={"status": "stopping"})
        if stopping.process and self._process_matches(stopping.process):
            try:
                os.killpg(stopping.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and self._pid_exists(stopping.process.pid):
                time.sleep(0.1)
            if self._pid_exists(stopping.process.pid) and self._process_matches(stopping.process):
                os.killpg(stopping.process.pid, signal.SIGKILL)
        stopped = self.store.read_status(run_id, binding)
        return self.store.transition_status(
            stopped,
            RuntimeState.STOPPED,
            clear_process=True,
            health={"status": "stopped", "orphan_detected": False},
        )

    def _health(self, binding: Any) -> dict[str, Any]:
        try:
            with urllib_request.urlopen(f"http://{binding.host}:{binding.port}/health", timeout=1.0) as response:
                data = response.read(64 * 1024)
                payload = json.loads(data.decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
        except (OSError, URLError, json.JSONDecodeError, TimeoutError):
            return {"status": "unavailable"}
        return {"status": "invalid"}

    def _port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    def _process_start_time(self, pid: int) -> str:
        stat = Path(f"/proc/{pid}/stat")
        if stat.is_file():
            return stat.read_text(encoding="utf-8").split()[21]
        return str(pid)

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _process_matches(self, process: ProcessIdentity) -> bool:
        if not self._pid_exists(process.pid):
            return False
        return self._process_start_time(process.pid) == process.process_start_time
