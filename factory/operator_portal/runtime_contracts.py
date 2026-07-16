from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any, Final


APP_ID: Final[str] = "upi_dispute_resolution"
GENERATED_RUN_ID: Final[str] = "first_governed_generation_run_001"
CERTIFICATION_POSTURE: Final[str] = "certification-ready-not-certified"
RUNTIME_APPROVAL_TOKEN: Final[str] = "phase50-local-runtime-approval"
RUN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,80}$")


class RuntimeContractError(RuntimeError):
    pass


class RuntimeState(str, Enum):
    ABSENT = "ABSENT"
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    STALE = "STALE"


TERMINAL_STATES: Final[set[RuntimeState]] = {
    RuntimeState.ABSENT,
    RuntimeState.STOPPED,
    RuntimeState.FAILED,
    RuntimeState.STALE,
}

VALID_TRANSITIONS: Final[dict[RuntimeState, set[RuntimeState]]] = {
    RuntimeState.ABSENT: {RuntimeState.STARTING, RuntimeState.STOPPED, RuntimeState.STALE},
    RuntimeState.STOPPED: {RuntimeState.STARTING, RuntimeState.STALE},
    RuntimeState.STARTING: {RuntimeState.READY, RuntimeState.FAILED, RuntimeState.STOPPING, RuntimeState.STALE},
    RuntimeState.READY: {RuntimeState.DEGRADED, RuntimeState.STOPPING, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.DEGRADED: {RuntimeState.READY, RuntimeState.STOPPING, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.STOPPING: {RuntimeState.STOPPED, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.FAILED: {RuntimeState.STARTING, RuntimeState.STALE},
    RuntimeState.STALE: {RuntimeState.STOPPED, RuntimeState.STARTING},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def transition_state(current: RuntimeState, target: RuntimeState) -> RuntimeState:
    if target not in VALID_TRANSITIONS[current]:
        raise RuntimeContractError(f"Invalid runtime transition {current.value} -> {target.value}")
    return target


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RuntimeContractError("run_id is not a governed runtime identifier")
    return run_id


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    process_start_time: str
    executable: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeBinding:
    run_id: str
    generated_run_id: str
    app_id: str
    manifest_sha256: str
    application_root: str
    entrypoint: str
    host: str
    port: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeStatus:
    state: RuntimeState
    binding: RuntimeBinding
    process: ProcessIdentity | None
    health: dict[str, Any]
    updated_at_utc: str
    mock_safe_local: bool = True
    real_payment_calls: str = "disabled"
    default_runtime_llm_calls: int = 0
    certification_posture: str = CERTIFICATION_POSTURE

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


@dataclass(frozen=True)
class ApprovalGrant:
    run_id: str
    action: str
    nonce: str
    approved_at_utc: str
    token_sha256: str
    consumed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def approval_secret() -> str:
    return os.getenv("UPI_APP_FACTORY_RUNTIME_APPROVAL_TOKEN", RUNTIME_APPROVAL_TOKEN)


def scoped_approval_digest(*, run_id: str, action: str, nonce: str, token: str) -> str:
    material = f"{validate_run_id(run_id)}:{action}:{nonce}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), material, hashlib.sha256).hexdigest()


def verify_scoped_approval(
    *,
    run_id: str,
    action: str,
    nonce: str,
    presented_token: str,
    expected_sha256: str,
) -> bool:
    actual = scoped_approval_digest(
        run_id=run_id,
        action=action,
        nonce=nonce,
        token=presented_token,
    )
    return hmac.compare_digest(actual, expected_sha256)


def safe_relative_path(path: Path, root: Path) -> str:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(resolved_root):
        raise RuntimeContractError(f"unsafe path outside runtime root: {path}")
    relative = resolved.relative_to(resolved_root).as_posix()
    if relative.startswith("../") or ".." in Path(relative).parts or Path(relative).is_absolute():
        raise RuntimeContractError(f"unsafe relative path: {relative}")
    return relative
