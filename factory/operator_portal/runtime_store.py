from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import secrets
import threading
from typing import Any, cast

from factory.operator_portal.runtime_contracts import (
    APP_ID,
    GENERATED_RUN_ID,
    ApprovalGrant,
    RuntimeBinding,
    RuntimeState,
    RuntimeStatus,
    ProcessIdentity,
    RuntimeContractError,
    approval_secret,
    parse_utc,
    sha256_bytes,
    transition_state,
    utc_now,
    validate_run_id,
    verify_scoped_approval,
)


class RuntimeStore:
    def __init__(self, *, project_root: Path, state_root: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.state_root = (
            state_root
            or self.project_root
            / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase50/runtime_state"
        ).resolve()
        if not self.state_root.is_relative_to(self.project_root) and not self.state_root.is_relative_to(Path("/tmp")):
            raise RuntimeContractError("runtime state root must stay in the worktree or /tmp")
        self._lock = threading.RLock()

    def run_dir(self, run_id: str) -> Path:
        validate_run_id(run_id)
        path = self.state_root / run_id
        resolved = path.resolve()
        if not resolved.is_relative_to(self.state_root):
            raise RuntimeContractError("runtime run path traversal rejected")
        return resolved

    def state_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "runtime_state.json"

    def events_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "runtime_events.jsonl"

    def scenario_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "scenario_results.json"

    def approvals_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "runtime_approvals.json"

    def log_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "runtime_stdout.log"

    def data_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "app_data"

    def read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise RuntimeContractError(f"expected object in {path}")
        return cast(dict[str, Any], value)

    def atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            path = self.events_path(run_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            sequence = 1
            if path.exists():
                sequence += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
            event = {
                "sequence": sequence,
                "recorded_at_utc": utc_now(),
                "event_type": event_type,
                "payload": redact(payload),
                "event_sha256": "",
            }
            event["event_sha256"] = sha256_bytes(
                json.dumps({k: v for k, v in event.items() if k != "event_sha256"}, sort_keys=True).encode("utf-8")
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
            return event

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.events_path(run_id)
        if not path.is_file():
            return []
        return [cast(dict[str, Any], json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_status(self, run_id: str, binding: RuntimeBinding) -> RuntimeStatus:
        path = self.state_path(run_id)
        if not path.is_file():
            return RuntimeStatus(
                state=RuntimeState.ABSENT,
                binding=binding,
                process=None,
                health={"status": "absent"},
                updated_at_utc=utc_now(),
            )
        payload = self.read_json(path)
        process_payload = payload.get("process")
        process = None
        if isinstance(process_payload, dict):
            process = ProcessIdentity(
                pid=int(process_payload["pid"]),
                process_start_time=str(process_payload["process_start_time"]),
                executable=str(process_payload["executable"]),
            )
        return RuntimeStatus(
            state=RuntimeState(str(payload["state"])),
            binding=binding,
            process=process,
            health=cast(dict[str, Any], payload.get("health", {})),
            updated_at_utc=str(payload.get("updated_at_utc", utc_now())),
        )

    def write_status(self, status: RuntimeStatus) -> None:
        self.atomic_write_json(self.state_path(status.binding.run_id), status.as_dict())

    def transition_status(
        self,
        status: RuntimeStatus,
        target: RuntimeState,
        *,
        process: ProcessIdentity | None = None,
        clear_process: bool = False,
        health: dict[str, Any] | None = None,
    ) -> RuntimeStatus:
        transition_state(status.state, target)
        next_status = RuntimeStatus(
            state=target,
            binding=status.binding,
            process=None if clear_process else process if process is not None else status.process,
            health=health if health is not None else status.health,
            updated_at_utc=utc_now(),
        )
        self.write_status(next_status)
        self.append_event(status.binding.run_id, "runtime_state_transition", next_status.as_dict())
        return next_status

    def create_approval(self, grant: ApprovalGrant) -> None:
        with self._lock:
            data = {"schema_version": "1.0", "approvals": []}
            path = self.approvals_path(grant.run_id)
            if path.exists():
                data = self.read_json(path)
            approvals = cast(list[dict[str, Any]], data.setdefault("approvals", []))
            approvals.append(grant.as_dict())
            self.atomic_write_json(path, data)
        self.append_event(grant.run_id, "runtime_approval_recorded", {"action": grant.action, "nonce": grant.nonce})

    def consume_approval(self, *, run_id: str, action: str, nonce: str) -> ApprovalGrant:
        with self._lock:
            path = self.approvals_path(run_id)
            if not path.is_file():
                raise RuntimeContractError("approval is required")
            data = self.read_json(path)
            approvals = cast(list[dict[str, Any]], data.get("approvals", []))
            for item in approvals:
                if item.get("run_id") == run_id and item.get("action") == action and item.get("nonce") == nonce:
                    if item.get("consumed"):
                        raise RuntimeContractError("approval replay rejected")
                    approved_at_utc = str(item.get("approved_at_utc", ""))
                    expires_at_utc = str(item.get("expires_at_utc", ""))
                    if parse_utc(expires_at_utc) <= datetime.now(timezone.utc):
                        raise RuntimeContractError("approval expired")
                    token_sha256 = str(item.get("token_sha256", ""))
                    if not verify_scoped_approval(
                        run_id=run_id,
                        action=action,
                        nonce=nonce,
                        presented_token=approval_secret(),
                        expected_sha256=token_sha256,
                    ):
                        raise RuntimeContractError("approval digest verification failed")
                    item["consumed"] = True
                    self.atomic_write_json(path, data)
                    grant = ApprovalGrant(
                        run_id=run_id,
                        action=action,
                        nonce=nonce,
                        approved_at_utc=approved_at_utc,
                        expires_at_utc=expires_at_utc,
                        token_sha256=token_sha256,
                        consumed=True,
                    )
                    self.append_event(run_id, "runtime_approval_consumed", {"action": action, "nonce": nonce})
                    return grant
            raise RuntimeContractError("approval scope rejected")


def default_binding(project_root: Path, *, run_id: str, port: int = 18042) -> RuntimeBinding:
    app_root = (
        project_root
        / "workspace/factory_generated/upi_dispute_resolution/generated_application"
    ).resolve()
    manifest = (
        project_root
        / "workspace/factory_generated/upi_dispute_resolution/generation_runs/first_governed_generation_run_001/generation_run_manifest.json"
    ).resolve()
    digest = sha256_bytes(manifest.read_bytes()) if manifest.is_file() else sha256_bytes(b"missing-manifest")
    return RuntimeBinding(
        run_id=validate_run_id(run_id),
        generated_run_id=GENERATED_RUN_ID,
        app_id=APP_ID,
        manifest_sha256=digest,
        application_root=app_root.as_posix(),
        entrypoint="generated_application.app.interfaces.api.main:app",
        host="127.0.0.1",
        port=port,
    )


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if "token" in str(k).lower() or "secret" in str(k).lower() else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        cleaned = value.replace("\r", "\\r").replace("\n", "\\n")
        if len(cleaned) > 4096:
            return cleaned[:4096] + "...[TRUNCATED]"
        return cleaned
    return value
