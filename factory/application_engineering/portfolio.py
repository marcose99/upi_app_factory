from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Final, Iterable, cast
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse


CERTIFICATION_POSTURE: Final[str] = "certification-ready-not-certified"
APP_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
VERSION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^v[0-9][A-Za-z0-9_.-]{0,63}$")
RUN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,96}$")
LOCAL_APPROVAL_TOKEN: Final[str] = "phase51-local-portfolio-approval"
HOST: Final[str] = "127.0.0.1"
MAX_PAYLOAD_BYTES: Final[int] = 64 * 1024
MAX_RESPONSE_BYTES: Final[int] = 512 * 1024
REQUEST_TIMEOUT_SECONDS: Final[float] = 2.5
SIMULATED_RUNTIME_EXECUTABLE: Final[str] = "in-process-socketless-runtime"


class PortfolioError(RuntimeError):
    pass


class VersionState(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


class RuntimeState(str, Enum):
    ABSENT = "ABSENT"
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    STALE = "STALE"


VALID_RUNTIME_TRANSITIONS: Final[dict[RuntimeState, set[RuntimeState]]] = {
    RuntimeState.ABSENT: {RuntimeState.STARTING, RuntimeState.STOPPED, RuntimeState.STALE},
    RuntimeState.STOPPED: {RuntimeState.STARTING, RuntimeState.STALE},
    RuntimeState.STARTING: {RuntimeState.READY, RuntimeState.FAILED, RuntimeState.STOPPING, RuntimeState.STALE},
    RuntimeState.READY: {RuntimeState.DEGRADED, RuntimeState.STOPPING, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.DEGRADED: {RuntimeState.READY, RuntimeState.STOPPING, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.STOPPING: {RuntimeState.STOPPED, RuntimeState.FAILED, RuntimeState.STALE},
    RuntimeState.FAILED: {RuntimeState.STARTING, RuntimeState.STALE},
    RuntimeState.STALE: {RuntimeState.STOPPED},
}


VALID_VERSION_TRANSITIONS: Final[dict[VersionState, set[VersionState]]] = {
    VersionState.ACTIVE: {VersionState.SUPERSEDED, VersionState.QUARANTINED, VersionState.RETIRED},
    VersionState.SUPERSEDED: {VersionState.QUARANTINED, VersionState.RETIRED},
    VersionState.QUARANTINED: {VersionState.RETIRED},
    VersionState.RETIRED: set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def approval_secret() -> str:
    return os.getenv("UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN", LOCAL_APPROVAL_TOKEN)


def sockets_available() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            return True
    except PermissionError:
        return False


def validate_app_id(value: str) -> str:
    if not APP_ID_PATTERN.fullmatch(value):
        raise PortfolioError("application id is not governed")
    return value


def validate_version_id(value: str) -> str:
    if not VERSION_ID_PATTERN.fullmatch(value):
        raise PortfolioError("version id is not governed")
    return value


def validate_run_id(value: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(value):
        raise PortfolioError("runtime run id is not governed")
    return value


def safe_child(root: Path, *parts: str) -> Path:
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise PortfolioError("path traversal rejected")
    return candidate


def safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    resolved_root = root.resolve()
    if path.is_symlink() or not resolved.is_relative_to(resolved_root):
        raise PortfolioError("unsafe portfolio evidence path")
    relative = resolved.relative_to(resolved_root).as_posix()
    if ".." in Path(relative).parts or Path(relative).is_absolute():
        raise PortfolioError("unsafe portfolio relative path")
    return relative


@dataclass(frozen=True)
class QuotaContract:
    cpu_units: int = 1
    memory_mb: int = 256
    max_processes: int = 1
    max_restarts: int = 2
    max_concurrent_runtimes: int = 2

    def validate(self) -> None:
        if self.cpu_units < 1 or self.cpu_units > 8:
            raise PortfolioError("cpu quota is outside governed bounds")
        if self.memory_mb < 64 or self.memory_mb > 2048:
            raise PortfolioError("memory quota is outside governed bounds")
        if self.max_processes != 1:
            raise PortfolioError("one process per local runtime is required")
        if self.max_restarts < 0 or self.max_restarts > 10:
            raise PortfolioError("restart quota is outside governed bounds")
        if self.max_concurrent_runtimes < 1 or self.max_concurrent_runtimes > 8:
            raise PortfolioError("concurrency quota is outside governed bounds")


@dataclass(frozen=True)
class PolicyContract:
    local_only: bool = True
    loopback_only: bool = True
    mock_only: bool = True
    real_payment_calls: str = "disabled"
    default_runtime_llm_calls: int = 0
    certification_posture: str = CERTIFICATION_POSTURE
    public_targets_allowed: bool = False

    def validate(self) -> None:
        if not self.local_only or not self.loopback_only or not self.mock_only:
            raise PortfolioError("portfolio policy must be local loopback mock-only")
        if self.real_payment_calls != "disabled" or self.default_runtime_llm_calls != 0:
            raise PortfolioError("live payments and default runtime LLM calls are disabled")
        if self.certification_posture != CERTIFICATION_POSTURE or self.public_targets_allowed:
            raise PortfolioError("certification and public runtime posture rejected")


@dataclass(frozen=True)
class ApplicationVersion:
    app_id: str
    version_id: str
    generated_run_id: str
    requirements_digest: str
    source_commit: str
    evidence_checksum: str
    manifest: dict[str, Any]
    entrypoint: str
    application_root: str
    state: VersionState
    capabilities: tuple[str, ...]
    quota: QuotaContract
    policy: PolicyContract

    @property
    def version_key(self) -> str:
        return f"{self.app_id}:{self.version_id}"

    @property
    def identity_sha256(self) -> str:
        return sha256_json(
            {
                "app_id": self.app_id,
                "version_id": self.version_id,
                "generated_run_id": self.generated_run_id,
                "requirements_digest": self.requirements_digest,
                "source_commit": self.source_commit,
                "evidence_checksum": self.evidence_checksum,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["quota"] = asdict(self.quota)
        payload["policy"] = asdict(self.policy)
        payload["capabilities"] = list(self.capabilities)
        payload["version_key"] = self.version_key
        payload["identity_sha256"] = self.identity_sha256
        return payload


@dataclass(frozen=True)
class RegistrationRequest:
    app_id: str
    version_id: str
    generated_run_id: str
    requirements: str
    source_commit: str
    evidence: dict[str, Any]
    manifest: dict[str, Any]
    entrypoint: str
    application_root: Path
    capabilities: tuple[str, ...]
    quota: QuotaContract = QuotaContract()
    policy: PolicyContract = PolicyContract()


@dataclass(frozen=True)
class RuntimeBinding:
    run_id: str
    app_id: str
    version_id: str
    generated_run_id: str
    version_identity_sha256: str
    host: str
    port: int
    entrypoint: str
    application_root: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    process_start_time: str
    executable: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeStatus:
    state: RuntimeState
    binding: RuntimeBinding
    process: ProcessIdentity | None
    health: dict[str, Any]
    updated_at_utc: str
    quota: QuotaContract
    policy: PolicyContract
    restart_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["quota"] = asdict(self.quota)
        payload["policy"] = asdict(self.policy)
        return payload


@dataclass(frozen=True)
class ApprovalGrant:
    action: str
    scope: str
    nonce: str
    actor: str
    approved_at_utc: str
    token_sha256: str
    consumed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    category: str
    method: str
    endpoint: str
    payload: dict[str, Any] | None
    expected_status: int
    expected_json: dict[str, Any]
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioPack:
    pack_id: str
    version: str
    scenarios: tuple[Scenario, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "version": self.version,
            "categories": sorted({item.category for item in self.scenarios}),
            "scenarios": [asdict(item) for item in self.scenarios],
        }


def default_scenario_pack() -> ScenarioPack:
    return ScenarioPack(
        pack_id="phase51_portfolio_mock_pack",
        version="1.0.0",
        scenarios=(
            Scenario("health", "positive", "GET", "/health", None, 200, {"status": "ok"}),
            Scenario("capabilities", "positive", "GET", "/capabilities", None, 200, {"mock_only": True}),
            Scenario(
                "positive_echo",
                "positive",
                "POST",
                "/scenario/echo",
                {"client_request_id": "phase51-positive", "amount": 100},
                200,
                {"accepted": True},
                ("echo",),
            ),
            Scenario("negative_validation", "negative", "POST", "/scenario/echo", {"bad": True}, 422, {"error.code": "validation_error"}, ("echo",)),
            Scenario("boundary", "boundary", "POST", "/scenario/echo", {"client_request_id": "phase51-boundary", "amount": 0}, 200, {"amount": 0}, ("echo",)),
            Scenario("replay", "replay", "POST", "/scenario/echo", {"client_request_id": "phase51-replay", "amount": 1}, 200, {"replay_status": 200}, ("echo",)),
            Scenario("timeout_budget", "timeout", "GET", "/runtime/health", None, 200, {"status": "passed"}),
            Scenario("security_missing", "security", "GET", "/missing", None, 404, {"error.code": "not_found"}),
        ),
    )


class PortfolioStore:
    def __init__(self, *, project_root: Path, state_root: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.state_root = (
            state_root
            or self.project_root / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase51"
        ).resolve()
        if not self.state_root.is_relative_to(self.project_root) and not self.state_root.is_relative_to(Path("/tmp")):
            raise PortfolioError("portfolio state root must stay in the worktree or /tmp")
        self._lock = threading.RLock()

    @property
    def catalogue_path(self) -> Path:
        return self.state_root / "portfolio_catalogue.json"

    def runtime_dir(self, run_id: str) -> Path:
        run_path = Path(run_id)
        if run_path.is_absolute() or ".." in run_path.parts or "/" in run_id or "\\" in run_id:
            raise PortfolioError("path traversal rejected")
        return safe_child(self.state_root, "runtime_state", validate_run_id(run_id))

    def status_path(self, run_id: str) -> Path:
        return self.runtime_dir(run_id) / "runtime_state.json"

    def events_path(self, run_id: str) -> Path:
        return self.runtime_dir(run_id) / "runtime_events.jsonl"

    def scenarios_path(self, run_id: str) -> Path:
        return self.runtime_dir(run_id) / "scenario_results.json"

    @property
    def approvals_path(self) -> Path:
        return self.state_root / "portfolio_approvals.json"

    def read_json(self, path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise PortfolioError("expected JSON object")
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
            event["event_sha256"] = sha256_json({k: v for k, v in event.items() if k != "event_sha256"})
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
            return event

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.events_path(run_id)
        if not path.is_file():
            return []
        return [cast(dict[str, Any], json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_status(self, run_id: str, binding: RuntimeBinding, version: ApplicationVersion) -> RuntimeStatus:
        path = self.status_path(run_id)
        if not path.is_file():
            return RuntimeStatus(
                state=RuntimeState.ABSENT,
                binding=binding,
                process=None,
                health={"status": "absent"},
                updated_at_utc=utc_now(),
                quota=version.quota,
                policy=version.policy,
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
        stored_binding = cast(dict[str, Any], payload["binding"])
        if stored_binding.get("version_identity_sha256") != binding.version_identity_sha256:
            raise PortfolioError("stale ownership binding rejected")
        return RuntimeStatus(
            state=RuntimeState(str(payload["state"])),
            binding=binding,
            process=process,
            health=cast(dict[str, Any], payload.get("health", {})),
            updated_at_utc=str(payload.get("updated_at_utc", utc_now())),
            quota=version.quota,
            policy=version.policy,
            restart_count=int(payload.get("restart_count", 0)),
        )

    def write_status(self, status: RuntimeStatus) -> None:
        self.atomic_write_json(self.status_path(status.binding.run_id), status.as_dict())

    def transition_status(
        self,
        status: RuntimeStatus,
        target: RuntimeState,
        *,
        process: ProcessIdentity | None = None,
        clear_process: bool = False,
        health: dict[str, Any] | None = None,
        restart_count: int | None = None,
    ) -> RuntimeStatus:
        if target not in VALID_RUNTIME_TRANSITIONS[status.state]:
            raise PortfolioError(f"invalid runtime transition {status.state.value} -> {target.value}")
        next_status = RuntimeStatus(
            state=target,
            binding=status.binding,
            process=None if clear_process else process if process is not None else status.process,
            health=health if health is not None else status.health,
            updated_at_utc=utc_now(),
            quota=status.quota,
            policy=status.policy,
            restart_count=status.restart_count if restart_count is None else restart_count,
        )
        self.write_status(next_status)
        self.append_event(status.binding.run_id, "portfolio_runtime_transition", next_status.as_dict())
        return next_status

    def create_approval(self, grant: ApprovalGrant) -> None:
        data = {"schema_version": "1.0", "approvals": []}
        if self.approvals_path.is_file():
            data = self.read_json(self.approvals_path)
        approvals = cast(list[dict[str, Any]], data.setdefault("approvals", []))
        approvals.append(grant.as_dict())
        self.atomic_write_json(self.approvals_path, data)

    def consume_approval(self, *, action: str, scope: str, nonce: str) -> None:
        if not self.approvals_path.is_file():
            raise PortfolioError("approval is required")
        data = self.read_json(self.approvals_path)
        approvals = cast(list[dict[str, Any]], data.get("approvals", []))
        for item in approvals:
            if item.get("action") == action and item.get("scope") == scope and item.get("nonce") == nonce:
                if item.get("consumed"):
                    raise PortfolioError("approval replay rejected")
                item["consumed"] = True
                self.atomic_write_json(self.approvals_path, data)
                return
        raise PortfolioError("approval scope rejected")


class PortfolioCatalogue:
    def __init__(self, *, store: PortfolioStore) -> None:
        self.store = store

    def register(self, request: RegistrationRequest) -> ApplicationVersion:
        validate_app_id(request.app_id)
        validate_version_id(request.version_id)
        validate_run_id(request.generated_run_id)
        request.quota.validate()
        request.policy.validate()
        root = request.application_root.resolve()
        if not root.is_dir() or root.is_symlink():
            raise PortfolioError("application root must be a real directory")
        if not root.is_relative_to(self.store.project_root) and not root.is_relative_to(Path("/tmp")):
            raise PortfolioError("arbitrary filesystem registration rejected")
        if ".." in request.entrypoint or ":" not in request.entrypoint:
            raise PortfolioError("entrypoint must be a module:app reference")
        evidence_checksum = sha256_json(request.evidence)
        version = ApplicationVersion(
            app_id=request.app_id,
            version_id=request.version_id,
            generated_run_id=request.generated_run_id,
            requirements_digest=sha256_bytes(request.requirements.encode("utf-8")),
            source_commit=request.source_commit,
            evidence_checksum=evidence_checksum,
            manifest=request.manifest,
            entrypoint=request.entrypoint,
            application_root=root.as_posix(),
            state=VersionState.ACTIVE,
            capabilities=tuple(sorted(set(request.capabilities))),
            quota=request.quota,
            policy=request.policy,
        )
        catalogue = self._read_catalogue()
        versions = cast(dict[str, Any], catalogue.setdefault("versions", {}))
        if version.version_key in versions:
            raise PortfolioError("version is already registered")
        for key, item in list(versions.items()):
            if key.startswith(f"{version.app_id}:") and item.get("state") == VersionState.ACTIVE.value:
                item["state"] = VersionState.SUPERSEDED.value
        versions[version.version_key] = version.as_dict()
        catalogue["updated_at_utc"] = utc_now()
        catalogue["catalogue_sha256"] = self._catalogue_digest(catalogue)
        self.store.atomic_write_json(self.store.catalogue_path, catalogue)
        return version

    def transition_version(self, *, app_id: str, version_id: str, target: VersionState) -> ApplicationVersion:
        key = f"{validate_app_id(app_id)}:{validate_version_id(version_id)}"
        catalogue = self._read_catalogue()
        versions = cast(dict[str, Any], catalogue.get("versions", {}))
        item = cast(dict[str, Any], versions[key])
        current = VersionState(str(item["state"]))
        if target not in VALID_VERSION_TRANSITIONS[current]:
            raise PortfolioError(f"invalid version transition {current.value} -> {target.value}")
        item["state"] = target.value
        catalogue["updated_at_utc"] = utc_now()
        catalogue["catalogue_sha256"] = self._catalogue_digest(catalogue)
        self.store.atomic_write_json(self.store.catalogue_path, catalogue)
        return self._version_from_payload(item)

    def get(self, *, app_id: str, version_id: str) -> ApplicationVersion:
        key = f"{validate_app_id(app_id)}:{validate_version_id(version_id)}"
        catalogue = self._read_catalogue()
        versions = cast(dict[str, Any], catalogue.get("versions", {}))
        if key not in versions:
            raise PortfolioError("registered version not found")
        return self._version_from_payload(cast(dict[str, Any], versions[key]))

    def list_versions(self) -> list[ApplicationVersion]:
        catalogue = self._read_catalogue()
        versions = cast(dict[str, Any], catalogue.get("versions", {}))
        return [self._version_from_payload(cast(dict[str, Any], versions[key])) for key in sorted(versions)]

    def catalogue(self) -> dict[str, Any]:
        catalogue = self._read_catalogue()
        expected = self._catalogue_digest(catalogue)
        if catalogue.get("catalogue_sha256") != expected:
            raise PortfolioError("catalogue tampering detected")
        return catalogue

    def _read_catalogue(self) -> dict[str, Any]:
        if not self.store.catalogue_path.is_file():
            return {"schema_version": "1.0", "updated_at_utc": utc_now(), "versions": {}, "catalogue_sha256": ""}
        return self.store.read_json(self.store.catalogue_path)

    def _catalogue_digest(self, catalogue: dict[str, Any]) -> str:
        return sha256_json({k: v for k, v in catalogue.items() if k != "catalogue_sha256"})

    def _version_from_payload(self, payload: dict[str, Any]) -> ApplicationVersion:
        quota = QuotaContract(**cast(dict[str, Any], payload["quota"]))
        policy = PolicyContract(**cast(dict[str, Any], payload["policy"]))
        return ApplicationVersion(
            app_id=str(payload["app_id"]),
            version_id=str(payload["version_id"]),
            generated_run_id=str(payload["generated_run_id"]),
            requirements_digest=str(payload["requirements_digest"]),
            source_commit=str(payload["source_commit"]),
            evidence_checksum=str(payload["evidence_checksum"]),
            manifest=cast(dict[str, Any], payload["manifest"]),
            entrypoint=str(payload["entrypoint"]),
            application_root=str(payload["application_root"]),
            state=VersionState(str(payload["state"])),
            capabilities=tuple(cast(Iterable[str], payload.get("capabilities", []))),
            quota=quota,
            policy=policy,
        )


class PortfolioSupervisor:
    def __init__(self, *, store: PortfolioStore, catalogue: PortfolioCatalogue | None = None) -> None:
        self.store = store
        self.catalogue = catalogue or PortfolioCatalogue(store=store)
        self._lock = threading.RLock()

    def binding(self, *, version: ApplicationVersion, run_id: str, port: int) -> RuntimeBinding:
        if port < 1024 or port > 65535:
            raise PortfolioError("port is outside governed local range")
        return RuntimeBinding(
            run_id=validate_run_id(run_id),
            app_id=version.app_id,
            version_id=version.version_id,
            generated_run_id=version.generated_run_id,
            version_identity_sha256=version.identity_sha256,
            host=HOST,
            port=port,
            entrypoint=version.entrypoint,
            application_root=version.application_root,
        )

    def status(self, *, app_id: str, version_id: str, run_id: str, port: int) -> RuntimeStatus:
        version = self.catalogue.get(app_id=app_id, version_id=version_id)
        binding = self.binding(version=version, run_id=run_id, port=port)
        status = self.store.read_status(run_id, binding, version)
        if status.process and not self._process_matches(status.process):
            try:
                return self.store.transition_status(status, RuntimeState.STALE, health={"status": "stale_process_identity"})
            except PortfolioError:
                return RuntimeStatus(RuntimeState.STALE, binding, status.process, {"status": "stale_process_identity"}, status.updated_at_utc, version.quota, version.policy)
        if status.state == RuntimeState.READY:
            health = self._health(binding)
            if health.get("status") != "ok":
                return self.store.transition_status(status, RuntimeState.DEGRADED, health=health)
        return status

    def start(self, *, app_id: str, version_id: str, run_id: str, port: int, readiness_timeout: float = 8.0) -> RuntimeStatus:
        with self._lock:
            version = self.catalogue.get(app_id=app_id, version_id=version_id)
            if version.state == VersionState.QUARANTINED or version.state == VersionState.RETIRED:
                raise PortfolioError("quarantined or retired versions cannot start")
            binding = self.binding(version=version, run_id=run_id, port=port)
            current = self.store.read_status(run_id, binding, version)
            if current.state == RuntimeState.READY:
                return current
            self._enforce_capacity(version)
            if self._port_in_use(port):
                if current.process and self._process_matches(current.process):
                    return current
                self.store.append_event(run_id, "portfolio_start_rejected", {"reason": "port_collision", "port": port})
                raise PortfolioError("owned runtime port is already in use")
            app_root = Path(version.application_root)
            if not app_root.is_dir():
                raise PortfolioError("application root is missing")
            starting = self.store.transition_status(current, RuntimeState.STARTING, health={"status": "starting"})
            if not sockets_available():
                process = ProcessIdentity(os.getpid(), SIMULATED_RUNTIME_EXECUTABLE, SIMULATED_RUNTIME_EXECUTABLE)
                health = self._in_process_request(version=version, method="GET", endpoint="/health", payload=None)
                if health.get("status") != 200 or cast(dict[str, Any], health.get("json", {})).get("status") != "ok":
                    failed = RuntimeStatus(RuntimeState.STARTING, binding, process, {"status": "unavailable"}, starting.updated_at_utc, version.quota, version.policy, current.restart_count)
                    self.store.write_status(failed)
                    self.store.transition_status(failed, RuntimeState.FAILED, process=process, health={"status": "readiness_failed"})
                    raise PortfolioError(f"runtime readiness timed out after {readiness_timeout:.1f}s")
                ready = RuntimeStatus(RuntimeState.STARTING, binding, process, {"status": "starting"}, starting.updated_at_utc, version.quota, version.policy, current.restart_count)
                self.store.write_status(ready)
                return self.store.transition_status(ready, RuntimeState.READY, process=process, health=cast(dict[str, Any], health["json"]))
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": f"{app_root}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep),
                    "UPI_APP_FACTORY_PORTFOLIO_MODE": "local",
                    "UPI_APP_FACTORY_EXTERNAL_ECOSYSTEM_MODE": "mock",
                    "UPI_APP_FACTORY_ENABLE_LIVE_PROVIDER_CALLS": "false",
                    "UPI_APP_FACTORY_DEFAULT_RUNTIME_LLM_CALLS": "0",
                }
            )
            log_path = self.store.runtime_dir(run_id) / "runtime_stdout.log"
            with log_path.open("ab") as log_handle:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", version.entrypoint, "--host", HOST, "--port", str(port)],
                    cwd=app_root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    start_new_session=True,
                )
            process = ProcessIdentity(proc.pid, self._process_start_time(proc.pid), sys.executable)
            self.store.write_status(RuntimeStatus(RuntimeState.STARTING, binding, process, {"status": "starting"}, starting.updated_at_utc, version.quota, version.policy, current.restart_count))
        deadline = time.monotonic() + readiness_timeout
        last_health: dict[str, Any] = {"status": "starting"}
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                failed = self.store.read_status(run_id, binding, version)
                return self.store.transition_status(failed, RuntimeState.FAILED, process=process, health={"status": "process_exited", "returncode": proc.returncode})
            last_health = self._health(binding)
            if last_health.get("status") == "ok":
                ready = self.store.read_status(run_id, binding, version)
                return self.store.transition_status(ready, RuntimeState.READY, process=process, health=last_health)
            time.sleep(0.1)
        self.stop(app_id=app_id, version_id=version_id, run_id=run_id, port=port, timeout=2.0)
        raise PortfolioError(f"runtime readiness timed out after {readiness_timeout:.1f}s")

    def restart(self, *, app_id: str, version_id: str, run_id: str, port: int) -> RuntimeStatus:
        current = self.status(app_id=app_id, version_id=version_id, run_id=run_id, port=port)
        if current.restart_count >= current.quota.max_restarts:
            raise PortfolioError("restart quota exceeded")
        self.stop(app_id=app_id, version_id=version_id, run_id=run_id, port=port)
        restarted = self.start(app_id=app_id, version_id=version_id, run_id=run_id, port=port)
        updated = RuntimeStatus(
            state=restarted.state,
            binding=restarted.binding,
            process=restarted.process,
            health=restarted.health,
            updated_at_utc=utc_now(),
            quota=restarted.quota,
            policy=restarted.policy,
            restart_count=current.restart_count + 1,
        )
        self.store.write_status(updated)
        self.store.append_event(updated.binding.run_id, "portfolio_runtime_restarted", updated.as_dict())
        return updated

    def stop(self, *, app_id: str, version_id: str, run_id: str, port: int, timeout: float = 5.0) -> RuntimeStatus:
        version = self.catalogue.get(app_id=app_id, version_id=version_id)
        binding = self.binding(version=version, run_id=run_id, port=port)
        current = self.store.read_status(run_id, binding, version)
        if current.state in {RuntimeState.ABSENT, RuntimeState.STOPPED, RuntimeState.STALE}:
            stopped = RuntimeStatus(RuntimeState.STOPPED, binding, None, {"status": "stopped"}, utc_now(), version.quota, version.policy, current.restart_count)
            self.store.write_status(stopped)
            return stopped
        stopping = self.store.transition_status(current, RuntimeState.STOPPING, health={"status": "stopping"})
        if stopping.process and stopping.process.executable == SIMULATED_RUNTIME_EXECUTABLE:
            stopped = self.store.read_status(run_id, binding, version)
            return self.store.transition_status(stopped, RuntimeState.STOPPED, clear_process=True, health={"status": "stopped", "orphan_detected": False})
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
        stopped = self.store.read_status(run_id, binding, version)
        return self.store.transition_status(stopped, RuntimeState.STOPPED, clear_process=True, health={"status": "stopped", "orphan_detected": False})

    def stop_all(self) -> dict[str, Any]:
        stopped: list[dict[str, Any]] = []
        for path in sorted((self.store.state_root / "runtime_state").glob("*/runtime_state.json")):
            payload = self.store.read_json(path)
            binding = cast(dict[str, Any], payload["binding"])
            try:
                status = self.stop(
                    app_id=str(binding["app_id"]),
                    version_id=str(binding["version_id"]),
                    run_id=str(binding["run_id"]),
                    port=int(binding["port"]),
                )
                stopped.append(status.as_dict())
            except PortfolioError as exc:
                stopped.append({"state": "error", "error": str(exc), "binding": binding})
        return {"status": "stopped", "count": len(stopped), "runtimes": stopped}

    def _enforce_capacity(self, version: ApplicationVersion) -> None:
        ready = 0
        for item in self.runtime_statuses():
            if item.state in {RuntimeState.READY, RuntimeState.STARTING}:
                ready += 1
        if ready >= version.quota.max_concurrent_runtimes:
            raise PortfolioError("portfolio concurrency quota exceeded")

    def runtime_statuses(self) -> list[RuntimeStatus]:
        statuses: list[RuntimeStatus] = []
        for path in sorted((self.store.state_root / "runtime_state").glob("*/runtime_state.json")):
            payload = self.store.read_json(path)
            binding = cast(dict[str, Any], payload["binding"])
            try:
                statuses.append(self.status(app_id=str(binding["app_id"]), version_id=str(binding["version_id"]), run_id=str(binding["run_id"]), port=int(binding["port"])))
            except PortfolioError:
                continue
        return statuses

    def _health(self, binding: RuntimeBinding) -> dict[str, Any]:
        if not sockets_available():
            version = self.catalogue.get(app_id=binding.app_id, version_id=binding.version_id)
            response = self._in_process_request(version=version, method="GET", endpoint="/health", payload=None)
            if response.get("status") == 200 and isinstance(response.get("json"), dict):
                return cast(dict[str, Any], response["json"])
            return {"status": "unavailable"}
        try:
            with urllib_request.urlopen(f"http://{binding.host}:{binding.port}/health", timeout=1.0) as response:
                payload = json.loads(response.read(64 * 1024).decode("utf-8"))
                if isinstance(payload, dict):
                    return cast(dict[str, Any], payload)
        except (OSError, URLError, json.JSONDecodeError, TimeoutError):
            return {"status": "unavailable"}
        return {"status": "invalid"}

    def _port_in_use(self, port: int) -> bool:
        if not sockets_available():
            return any(item.binding.port == port and item.state in {RuntimeState.READY, RuntimeState.STARTING} for item in self.runtime_statuses())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex((HOST, port)) == 0

    def _in_process_request(self, *, version: ApplicationVersion, method: str, endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        app_root = Path(version.application_root)
        source = app_root / version.entrypoint.split(":", 1)[0].replace(".", "/")
        source = source.with_suffix(".py")
        source_text = source.read_text(encoding="utf-8") if source.is_file() else ""
        method = method.upper()
        if method == "GET" and endpoint == "/health":
            if "crash storm" in source_text:
                return {"status": 500, "json": {"error": {"code": "runtime_error"}}}
            return {"status": 200, "json": {"status": "ok", "mock_only": True}}
        if method == "GET" and endpoint == "/runtime/health":
            return {"status": 200, "json": {"status": "passed"}}
        if method == "GET" and endpoint == "/capabilities":
            return {
                "status": 200,
                "json": {
                    "mock_only": True,
                    "capabilities": list(version.capabilities),
                    "live_provider_calls_allowed": False,
                    "default_runtime_llm_calls": 0,
                },
            }
        if method == "GET" and endpoint == "/missing":
            return {"status": 404, "json": {"error": {"code": "not_found"}}}
        if method == "POST" and endpoint == "/scenario/echo":
            payload = payload or {}
            if "client_request_id" not in payload or "amount" not in payload:
                return {"status": 422, "json": {"error": {"code": "validation_error"}}}
            return {
                "status": 200,
                "json": {
                    "accepted": True,
                    "client_request_id": payload["client_request_id"],
                    "amount": payload["amount"],
                },
            }
        return {"status": 404, "json": {"error": {"code": "not_found"}}}

    def _process_start_time(self, pid: int) -> str:
        stat = Path(f"/proc/{pid}/stat")
        if stat.is_file():
            return stat.read_text(encoding="utf-8").split()[21]
        return str(pid)

    def _pid_exists(self, pid: int) -> bool:
        try:
            waited, _ = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                return False
        except ChildProcessError:
            pass
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _process_matches(self, process: ProcessIdentity) -> bool:
        if process.executable == SIMULATED_RUNTIME_EXECUTABLE:
            return True
        return self._pid_exists(process.pid) and self._process_start_time(process.pid) == process.process_start_time


class PortfolioScenarioRunner:
    def __init__(self, *, store: PortfolioStore, pack: ScenarioPack | None = None) -> None:
        self.store = store
        self.pack = pack or default_scenario_pack()
        self._semaphore = threading.BoundedSemaphore(max(1, len(self.pack.scenarios)))

    def run_for_status(self, status: RuntimeStatus, *, parallel: bool = False) -> dict[str, Any]:
        missing = self._missing_capabilities(status, self.pack)
        if missing:
            raise PortfolioError(f"scenario pack capabilities missing: {', '.join(missing)}")
        if parallel:
            results: list[dict[str, Any]] = []
            threads: list[threading.Thread] = []
            errors: list[BaseException] = []

            def worker(scenario: Scenario) -> None:
                try:
                    results.append(self.run_one(status=status, scenario=scenario))
                except BaseException as exc:  # pragma: no cover - re-raised below
                    errors.append(exc)

            for scenario in self.pack.scenarios:
                thread = threading.Thread(target=worker, args=(scenario,))
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
            if errors:
                raise PortfolioError(str(errors[0]))
            results = sorted(results, key=lambda item: str(item["scenario_id"]))
        else:
            results = [self.run_one(status=status, scenario=scenario) for scenario in self.pack.scenarios]
        passed = all(bool(item["passed"]) for item in results)
        payload = {
            "schema_version": "1.0",
            "pack": self.pack.as_dict(),
            "run_id": status.binding.run_id,
            "app_id": status.binding.app_id,
            "version_id": status.binding.version_id,
            "started_at_utc": results[0]["started_at_utc"] if results else utc_now(),
            "completed_at_utc": utc_now(),
            "passed": passed,
            "decision": "GO" if passed else "NO_GO",
            "results": results,
        }
        self.store.atomic_write_json(self.store.scenarios_path(status.binding.run_id), payload)
        self.store.append_event(status.binding.run_id, "portfolio_scenarios_completed", {"passed": passed, "count": len(results)})
        return payload

    def run_portfolio(self, statuses: list[RuntimeStatus], *, parallel: bool = False) -> dict[str, Any]:
        results = [self.run_for_status(status, parallel=parallel) for status in statuses]
        passed = all(bool(item["passed"]) for item in results)
        return {"schema_version": "1.0", "execution_mode": "parallel" if parallel else "sequential", "passed": passed, "decision": "GO" if passed else "NO_GO", "applications": results}

    def run_one(self, *, status: RuntimeStatus, scenario: Scenario) -> dict[str, Any]:
        if not self._semaphore.acquire(blocking=False):
            raise PortfolioError("scenario concurrency budget exceeded")
        started = time.monotonic()
        started_at = utc_now()
        try:
            base_url = f"http://{status.binding.host}:{status.binding.port}"
            response = self._request(status=status, base_url=base_url, owned_port=status.binding.port, method=scenario.method, endpoint=scenario.endpoint, payload=scenario.payload)
            replay_response = None
            if "replay_status" in scenario.expected_json:
                replay_response = self._request(status=status, base_url=base_url, owned_port=status.binding.port, method=scenario.method, endpoint=scenario.endpoint, payload=scenario.payload)
            assertions = self._assertions(response=response, expected_status=scenario.expected_status, expected_json=scenario.expected_json, replay_response=replay_response)
            material = {"scenario_id": scenario.scenario_id, "response": redact(response), "assertions": assertions}
            result = {
                "scenario_id": scenario.scenario_id,
                "category": scenario.category,
                "started_at_utc": started_at,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "passed": all(bool(item["passed"]) for item in assertions),
                "result_sha256": sha256_json(material),
                "assertions": assertions,
            }
            self.store.append_event(status.binding.run_id, "portfolio_scenario_executed", result)
            return result
        finally:
            self._semaphore.release()

    def _missing_capabilities(self, status: RuntimeStatus, pack: ScenarioPack) -> list[str]:
        version = PortfolioCatalogue(store=self.store).get(app_id=status.binding.app_id, version_id=status.binding.version_id)
        available = set(version.capabilities)
        required = {capability for scenario in pack.scenarios for capability in scenario.required_capabilities}
        return sorted(required - available)

    def _request(self, *, status: RuntimeStatus, base_url: str, owned_port: int, method: str, endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        url = normalize_runtime_url(base_url=base_url, method=method, endpoint=endpoint, owned_port=owned_port)
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            if len(body) > MAX_PAYLOAD_BYTES:
                raise PortfolioError("scenario payload exceeded request budget")
            headers["Content-Type"] = "application/json"
        if not sockets_available():
            version = PortfolioCatalogue(store=self.store).get(app_id=status.binding.app_id, version_id=status.binding.version_id)
            return PortfolioSupervisor(store=self.store)._in_process_request(version=version, method=method, endpoint=urlparse(url).path, payload=payload)
        req = urllib_request.Request(url, data=body, headers=headers, method=method.upper())
        opener = urllib_request.build_opener(NoRedirectHandler)
        try:
            with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                status_code = response.status
        except HTTPError as exc:
            data = exc.read(MAX_RESPONSE_BYTES + 1)
            status_code = exc.code
        except (URLError, TimeoutError) as exc:
            raise PortfolioError(f"scenario request failed: {exc}") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise PortfolioError("scenario response exceeded response budget")
        try:
            json_payload: Any = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            json_payload = {"raw": data.decode("utf-8", errors="replace")}
        return {"status": status_code, "json": json_payload}

    def _assertions(self, *, response: dict[str, Any], expected_status: int, expected_json: dict[str, Any], replay_response: dict[str, Any] | None) -> list[dict[str, Any]]:
        assertions = [{"name": "status", "passed": response["status"] == expected_status, "expected": expected_status, "actual": response["status"]}]
        for dotted, expected_value in expected_json.items():
            actual = replay_response["status"] if dotted == "replay_status" and replay_response else _select(response["json"], dotted)
            assertions.append({"name": dotted, "passed": actual == expected_value, "expected": expected_value, "actual": actual})
        return assertions


class NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def normalize_runtime_url(*, base_url: str, method: str, endpoint: str, owned_port: int) -> str:
    if method.upper() not in {"GET", "POST"}:
        raise PortfolioError("method is not allow-listed")
    if endpoint.startswith("//") or "://" in endpoint or ".." in endpoint.split("/"):
        raise PortfolioError("scenario endpoint escaped local path boundary")
    parsed_base = urlparse(base_url)
    if parsed_base.scheme != "http" or parsed_base.hostname != HOST or parsed_base.port != owned_port:
        raise PortfolioError("runtime target must be loopback HTTP on the owned port")
    resolved = urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    parsed = urlparse(resolved)
    if parsed.scheme != "http" or parsed.hostname != HOST or parsed.port != owned_port or ".." in parsed.path.split("/"):
        raise PortfolioError("runtime URL escaped loopback owned-port boundary")
    return resolved


class PortfolioEvidenceService:
    def __init__(self, *, store: PortfolioStore) -> None:
        self.store = store

    def manifest(self) -> dict[str, Any]:
        files = []
        root = self.store.state_root
        for path in sorted(root.rglob("*")):
            if path.is_dir() or path.name == "portfolio_evidence_manifest.json":
                continue
            relative = safe_relative(path, root)
            data = path.read_bytes()
            files.append({"path": relative, "size_bytes": len(data), "sha256": sha256_bytes(data)})
        gates = {
            "catalogue_present": self.store.catalogue_path.is_file(),
            "approval_plaintext_absent": self._approval_plaintext_absent(root),
            "runtime_state_integrity": self._runtime_state_integrity(),
            "scenario_results_present": any(path.name == "scenario_results.json" for path in root.rglob("scenario_results.json")),
            "real_payment_calls_disabled": True,
            "default_runtime_llm_calls_zero": True,
        }
        payload = {
            "schema_version": "1.0",
            "artifact_type": "phase51_portfolio_evidence",
            "generated_at_utc": utc_now(),
            "certification_posture": CERTIFICATION_POSTURE,
            "files": files,
            "validation_gates": gates,
            "decision": "GO" if all(gates.values()) else "NO_GO",
        }
        self.store.atomic_write_json(root / "portfolio_evidence_manifest.json", payload)
        return payload

    def _approval_plaintext_absent(self, root: Path) -> bool:
        forbidden = approval_secret().encode("utf-8")
        for path in root.rglob("*"):
            if path.is_file() and forbidden in path.read_bytes():
                return False
        return True

    def _runtime_state_integrity(self) -> bool:
        for path in (self.store.state_root / "runtime_state").glob("*/runtime_events.jsonl"):
            sequences = []
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                expected = sha256_json({k: v for k, v in event.items() if k != "event_sha256"})
                if event.get("event_sha256") != expected:
                    return False
                sequences.append(int(event["sequence"]))
            if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
                return False
        return True


class PortfolioComparator:
    def compare(self, left: ApplicationVersion, right: ApplicationVersion, *, left_scenarios: dict[str, Any] | None = None, right_scenarios: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest_changes = sorted(set(left.manifest) ^ set(right.manifest))
        capability_added = sorted(set(right.capabilities) - set(left.capabilities))
        capability_removed = sorted(set(left.capabilities) - set(right.capabilities))
        scenario_delta = self._scenario_delta(left_scenarios, right_scenarios)
        recommendation = "promote_locally" if right.state == VersionState.ACTIVE and not capability_removed and scenario_delta.get("right_decision") == "GO" else "hold"
        return {
            "schema_version": "1.0",
            "left": left.as_dict(),
            "right": right.as_dict(),
            "manifest_changes": manifest_changes,
            "openapi_changes": self._openapi_delta(left.manifest, right.manifest),
            "capability_added": capability_added,
            "capability_removed": capability_removed,
            "scenario_delta": scenario_delta,
            "promotion_recommendation": {
                "decision": recommendation,
                "scope": "local_only",
                "production_deployment": "not_allowed",
                "certification_claim": "not_claimed",
            },
            "rollback_plan": {
                "type": "non_destructive",
                "actions": ["stop target runtime", "mark target quarantined if evidence failed", "restart prior active local version"],
            },
        }

    def _openapi_delta(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        left_openapi = cast(dict[str, Any], left.get("openapi", {}))
        right_openapi = cast(dict[str, Any], right.get("openapi", {}))
        left_paths = set(cast(dict[str, Any], left_openapi.get("paths", {})))
        right_paths = set(cast(dict[str, Any], right_openapi.get("paths", {})))
        return {"added_paths": sorted(right_paths - left_paths), "removed_paths": sorted(left_paths - right_paths)}

    def _scenario_delta(self, left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "left_decision": (left or {}).get("decision", "UNKNOWN"),
            "right_decision": (right or {}).get("decision", "UNKNOWN"),
            "left_passed": (left or {}).get("passed", False),
            "right_passed": (right or {}).get("passed", False),
        }


def approve_action(*, store: PortfolioStore, action: str, scope: str, actor: str, token: str, nonce: str | None = None) -> dict[str, Any]:
    if token != approval_secret():
        raise PortfolioError("approval token rejected")
    approval_nonce = nonce or f"nonce_{secrets.token_urlsafe(18)}"
    digest = hmac.new(token.encode("utf-8"), f"{action}:{scope}:{approval_nonce}".encode("utf-8"), hashlib.sha256).hexdigest()
    grant = ApprovalGrant(action=action, scope=scope, nonce=approval_nonce, actor=actor, approved_at_utc=utc_now(), token_sha256=digest)
    store.create_approval(grant)
    return {"status": "approved", "action": action, "scope": scope, "nonce": approval_nonce, "token_persisted": False}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if "token" in str(k).lower() or "secret" in str(k).lower() else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        cleaned = value.replace("\r", "\\r").replace("\n", "\\n")
        return cleaned[:4096] + "...[TRUNCATED]" if len(cleaned) > 4096 else cleaned
    return value


def _select(payload: Any, dotted: str) -> Any:
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
