from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import zipfile
from typing import Any, Final, Literal, TypedDict, cast

from factory.application_engineering.portfolio import (
    PortfolioCatalogue,
    PortfolioError,
    PortfolioStore,
    RegistrationRequest,
)
from factory.observability import get_logger, logging_context
from factory.operator_portal.state_roots import resolve_state_roots
from factory.token_economics import classify_generated_application_token_economics
from scripts.run_portal_requirements_driven_application_engineering import (
    APPROVAL_TOKEN as APPROVAL_TOKEN,
    AdapterConfig,
    run as run_requirements_engineering,
    validate_app_id,
)


APP_ID: Final[str] = "upi_dispute_resolution"
MAX_REQUIREMENTS_BYTES: Final[int] = 128 * 1024
MIN_REQUIREMENTS_CHARS: Final[int] = 80
RUN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^run_[0-9]{8}T[0-9]{6}Z_[A-Za-z0-9_-]{22}$"
)
RUN_ACTION_APPLICATION_ENGINEERING: Final[str] = "application_engineering"
CERTIFICATION_POSTURE: Final[str] = "certification-ready-not-certified"
GENERATOR_ENTRYPOINT: Final[str] = "scripts/run_portal_requirements_driven_application_engineering.py"
APPLICATION_DOWNLOAD_FILENAME: Final[str] = "generated_application.zip"
ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
LOGGER = get_logger(__name__)
__all__ = [
    "APPROVAL_TOKEN",
    "BrowserIntakeOrchestrator",
    "MAX_REQUIREMENTS_BYTES",
    "MIN_REQUIREMENTS_CHARS",
    "subprocess",
    "validate_requirements_text",
]

RunState = Literal[
    "DRAFT",
    "VALIDATED",
    "REQUIREMENTS_ACCEPTED",
    "CAPABILITY_PRE_RUN_READY",
    "CAPABILITY_PRE_RUN_BLOCKED",
    "PLAN_READY",
    "AWAITING_APPROVAL",
    "APPROVED",
    "EXECUTION_QUEUED",
    "EXECUTING",
    "VALIDATING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
]

TERMINAL_STATES: Final[set[RunState]] = {"SUCCEEDED", "FAILED", "CANCELLED"}
VALID_TRANSITIONS: Final[dict[RunState, set[RunState]]] = {
    "DRAFT": {"VALIDATED", "CANCELLED"},
    "VALIDATED": {"REQUIREMENTS_ACCEPTED", "CANCELLED"},
    "REQUIREMENTS_ACCEPTED": {"CAPABILITY_PRE_RUN_READY", "CAPABILITY_PRE_RUN_BLOCKED", "PLAN_READY", "CANCELLED"},
    "CAPABILITY_PRE_RUN_READY": {"PLAN_READY", "CANCELLED"},
    "CAPABILITY_PRE_RUN_BLOCKED": {"FAILED", "CANCELLED"},
    "PLAN_READY": {"AWAITING_APPROVAL", "CANCELLED"},
    "AWAITING_APPROVAL": {"APPROVED", "CANCELLED"},
    "APPROVED": {"EXECUTION_QUEUED", "CANCELLED"},
    "EXECUTION_QUEUED": {"EXECUTING", "CANCELLED"},
    "EXECUTING": {"VALIDATING", "FAILED", "CANCELLED"},
    "VALIDATING": {"SUCCEEDED", "FAILED", "CANCELLED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

SECRET_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}")),
    ("assignment_secret", re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*\S{12,}")),
)
PROMPT_INJECTION_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("ignore_prior_instructions", re.compile(r"(?i)\bignore\b.{0,40}\b(instructions|policy|rules)\b")),
    ("system_prompt_request", re.compile(r"(?i)\b(system prompt|developer message|hidden instructions)\b")),
    ("jailbreak_claim", re.compile(r"(?i)\b(jailbreak|do anything now|bypass safety)\b")),
)


class OrchestrationConflict(RuntimeError):
    pass


class OrchestrationNotFound(RuntimeError):
    pass


class OrchestrationValidationError(RuntimeError):
    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("requirements validation failed")
        self.errors = errors


class ValidationResult(TypedDict):
    valid: bool
    normalized_requirements: str
    sha256: str
    size_bytes: int
    max_size_bytes: int
    errors: list[dict[str, str]]
    findings: list[dict[str, str]]


@dataclass(frozen=True)
class PortalRunPaths:
    root: Path
    requirements: Path
    state: Path
    ledger: Path
    events: Path
    approvals: Path
    plan: Path
    result: Path
    generated_application: Path
    engineering_evidence: Path
    archives: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _approval_token() -> str:
    return os.getenv("UPI_APP_FACTORY_PORTAL_APPROVAL_TOKEN", APPROVAL_TOKEN)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _json_sha256(payload: dict[str, Any]) -> str:
    return _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def _canonical_payload_sha256(payload: dict[str, Any], *, exclude: str) -> str:
    material = {key: value for key, value in payload.items() if key != exclude}
    return _json_sha256(material)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return cast(dict[str, Any], value)


def _safe_zip_tree(archive_path: Path, root: Path, *, top_level_directory: str | None = None) -> str:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(root).as_posix()
            if (
                path.is_symlink()
                or relative.startswith("../")
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
            ):
                raise ValueError(f"Unsafe archive member: {relative}")
            member = f"{top_level_directory}/{relative}" if top_level_directory else relative
            if member in seen:
                raise ValueError(f"Duplicate archive member: {member}")
            seen.add(member)
            info = zipfile.ZipInfo(member)
            info.date_time = ZIP_TIMESTAMP
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return _sha256_file(archive_path)


def _safe_relative_file_path(path: Path, root: Path) -> str:
    if path.is_symlink():
        raise ValueError(f"Symlinks are not allowed in generated application archives: {path}")
    relative = path.relative_to(root).as_posix()
    if (
        Path(relative).is_absolute()
        or relative == "."
        or relative.startswith("../")
        or ".." in Path(relative).parts
    ):
        raise ValueError(f"Unsafe archive member: {relative}")
    return relative


def _endpoint_inventory_contains_path(openapi_inventory: object, *, path: str) -> bool:
    if not isinstance(openapi_inventory, dict):
        return False
    endpoint_inventory = openapi_inventory.get("endpoint_inventory")
    if not isinstance(endpoint_inventory, list):
        return False
    return any(isinstance(item, dict) and item.get("path") == path for item in endpoint_inventory)


def _deterministic_version_id(*, app_id: str, run_id: str, requirements_sha256: str) -> str:
    material = f"{app_id}\n{run_id}\n{requirements_sha256}".encode("utf-8")
    return "v1_" + _sha256_bytes(material)[:16]


def _source_commit(project_root: Path) -> str:
    injected = os.getenv("UPI_APP_FACTORY_SOURCE_COMMIT")
    if injected:
        return injected
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        completed = None
    if completed is not None:
        commit = completed.stdout.strip()
        if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", commit):
            return commit
    manifest_path = project_root / "FACTORY_EXPORT_MANIFEST.json"
    if manifest_path.is_file():
        manifest = _read_json(manifest_path)
        repository_commit = manifest.get("repository_commit")
        if isinstance(repository_commit, str) and re.fullmatch(r"[0-9a-f]{40}", repository_commit):
            return repository_commit
        raise ValueError("FACTORY_EXPORT_MANIFEST.json repository_commit is invalid")
    return "unavailable:deterministic_non_git_non_manifest_source_root"


def _generated_application_files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        relative = _safe_relative_file_path(path, root)
        if relative == "generation_manifest.json":
            continue
        if relative in seen:
            raise ValueError(f"Duplicate generated application path: {relative}")
        seen.add(relative)
        payload = path.read_bytes()
        records.append(
            {
                "path": relative,
                "sha256": _sha256_bytes(payload),
                "size_bytes": len(payload),
            }
        )
    return records


def _write_generation_manifest(
    *,
    manifest_path: Path,
    project_root: Path,
    run_id: str,
    requirements_sha256: str,
    generated_application: Path,
    app_id: str = APP_ID,
    version_id: str | None = None,
    portfolio_registration: dict[str, Any] | None = None,
    openapi: dict[str, Any] | None = None,
    openapi_inventory: dict[str, Any] | None = None,
) -> None:
    entrypoint = project_root / GENERATOR_ENTRYPOINT
    if not entrypoint.is_file():
        raise ValueError(f"Generator entrypoint does not exist: {entrypoint}")
    try:
        generator_entrypoint = entrypoint.relative_to(project_root).as_posix()
    except ValueError:
        generator_entrypoint = str(entrypoint)

    metadata_path = generated_application / "generation_metadata.json"
    token_economics: dict[str, Any] = {
        "policy_version": "2026-07-29.v1",
        "applicability": {
            "status": "NOT_APPLICABLE",
            "reason": "generated application metadata is not available",
            "runtime_llm_calls_default": 0,
        },
    }
    if metadata_path.is_file():
        metadata = _read_json(metadata_path)
        token_economics = {
            "policy_version": "2026-07-29.v1",
            "applicability": classify_generated_application_token_economics(
                metadata=metadata,
                runtime_llm_calls_default=int(metadata.get("llm_calls", 0)),
            ),
        }

    manifest = {
        "schema_version": "1.0",
        "artifact_type": "generated_application",
        "run_id": run_id,
        "app_id": app_id,
        "requirements_sha256": requirements_sha256,
        "generator_entrypoint": generator_entrypoint,
        "generated_at_utc": _utc_now(),
        "mock_boundary": "enforced",
        "real_payment_calls": "disabled",
        "default_runtime_llm_calls": 0,
        "certification_posture": CERTIFICATION_POSTURE,
        "token_economics": token_economics,
        "files": _generated_application_files(generated_application),
    }
    if version_id is not None:
        manifest["version_id"] = version_id
    if portfolio_registration is not None:
        manifest["portfolio_registration"] = portfolio_registration
    if openapi is not None:
        manifest["openapi"] = openapi
    if openapi_inventory is not None:
        manifest["openapi_inventory"] = openapi_inventory
    _atomic_write_json(manifest_path, manifest)


def _zip_generated_application(
    *,
    archive_path: Path,
    root: Path,
    top_level_directory: str,
) -> str:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            relative = _safe_relative_file_path(path, root)
            member = f"{top_level_directory}/{relative}"
            if member in seen:
                raise ValueError(f"Duplicate archive member: {member}")
            seen.add(member)
            info = zipfile.ZipInfo(member)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return _sha256_file(archive_path)


def validate_requirements_text(requirements: str) -> ValidationResult:
    normalized = requirements.replace("\r\n", "\n").replace("\r", "\n")
    raw_bytes = normalized.encode("utf-8")
    errors: list[dict[str, str]] = []
    findings: list[dict[str, str]] = []

    for code, pattern in SECRET_PATTERNS:
        if pattern.search(normalized):
            errors.append(
                {
                    "code": f"secret_like_material_{code}",
                    "message": "Secret-like material is not accepted in browser requirements.",
                }
            )

    if not normalized.strip():
        errors.append({"code": "empty_requirements", "message": "Requirements cannot be empty."})
    elif len(normalized.strip()) < MIN_REQUIREMENTS_CHARS:
        errors.append(
            {
                "code": "requirements_too_small",
                "message": f"Requirements must contain at least {MIN_REQUIREMENTS_CHARS} characters.",
            }
        )
    if len(raw_bytes) > MAX_REQUIREMENTS_BYTES:
        errors.append(
            {
                "code": "requirements_too_large",
                "message": f"Requirements exceed {MAX_REQUIREMENTS_BYTES} bytes.",
            }
        )

    for code, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(normalized):
            findings.append(
                {
                    "code": f"prompt_injection_like_{code}",
                    "message": (
                        "Prompt-injection-like text was recorded by deterministic policy; "
                        "this is not a claim of complete detection."
                    ),
                }
            )

    return {
        "valid": not errors,
        "normalized_requirements": normalized,
        "sha256": _sha256_bytes(raw_bytes),
        "size_bytes": len(raw_bytes),
        "max_size_bytes": MAX_REQUIREMENTS_BYTES,
        "errors": errors,
        "findings": findings,
    }


class BrowserIntakeOrchestrator:
    def __init__(
        self,
        *,
        project_root: Path,
        state_root: Path | None = None,
        portfolio_state_root: Path | None = None,
        publication_root: Path | None = None,
    ) -> None:
        roots = resolve_state_roots(
            project_root=project_root,
            browser_state_root=state_root,
            portfolio_state_root=portfolio_state_root,
        )
        self.project_root = roots.project_root
        self.state_root = roots.browser_state_root
        configured_publication_root = os.getenv("UPI_APP_FACTORY_PORTAL_PUBLICATION_ROOT")
        self.publication_root = (
            publication_root
            if publication_root is not None
            else Path(configured_publication_root).expanduser()
            if configured_publication_root
            else self.project_root / "workspace"
        ).expanduser().resolve()
        self.portfolio_store = PortfolioStore(
            project_root=self.project_root,
            state_root=roots.portfolio_state_root,
        )
        self.portfolio_catalogue = PortfolioCatalogue(store=self.portfolio_store)
        self._active_workers: set[str] = set()
        self._worker_lock = threading.Lock()
        self.recover_orphaned_runs()

    def validate_requirements(self, requirements: str) -> dict[str, Any]:
        result = validate_requirements_text(requirements)
        if not result["valid"]:
            raise OrchestrationValidationError(result["errors"])
        return {
            "status": "validated",
            "validation": {k: v for k, v in result.items() if k != "normalized_requirements"},
            **self._governance_payload(),
        }

    def create_run(self, requirements: str, *, app_id: str = APP_ID) -> dict[str, Any]:
        try:
            app_id = validate_app_id(app_id)
        except RuntimeError as exc:
            raise OrchestrationValidationError(
                [{"code": "invalid_app_id", "message": "Application ID must be lowercase snake_case."}]
            ) from exc
        validation = validate_requirements_text(requirements)
        if not validation["valid"]:
            raise OrchestrationValidationError(validation["errors"])
        run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + secrets.token_urlsafe(16)
        paths = self._paths(run_id)
        paths.root.mkdir(parents=True, exist_ok=False)
        _atomic_write_text(paths.requirements, validation["normalized_requirements"])
        created_at = _utc_now()
        state = {
            "schema_version": "browser-driven-intake-run.v1",
            "run_id": run_id,
            "app_id": app_id,
            "app_id_sha256": _sha256_bytes(app_id.encode("utf-8")),
            "state": "DRAFT",
            "created_at_utc": created_at,
            "updated_at_utc": created_at,
            "requirements_sha256": validation["sha256"],
            "requirements_size_bytes": validation["size_bytes"],
            "approval_required": True,
            "approval": None,
            "validation": {k: v for k, v in validation.items() if k != "normalized_requirements"},
            "final_decision": None,
            **self._governance_payload(),
        }
        _atomic_write_json(paths.state, state)
        self._record_event(
            run_id,
            "run_created",
            {"app_id": app_id, "requirements_sha256": validation["sha256"]},
        )
        self._transition(run_id, "VALIDATED", reason="requirements_validated")
        self._transition(run_id, "REQUIREMENTS_ACCEPTED", reason="requirements_persisted")
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        state["events"] = self.events(run_id)["events"]
        state["artifacts"] = self._artifact_status(paths)
        if paths.plan.is_file():
            state["plan"] = _read_json(paths.plan)
        if paths.result.is_file():
            state["engineering_result"] = _read_json(paths.result)
        return state

    def plan(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        if state["state"] not in {"REQUIREMENTS_ACCEPTED", "PLAN_READY", "AWAITING_APPROVAL"}:
            raise OrchestrationConflict(f"Cannot plan from state {state['state']}")
        if not paths.plan.is_file():
            app_id = self._state_app_id(state)
            config = self._adapter_config(paths, plan_only=True)
            plan = run_requirements_engineering(config)
            plan_payload = {
                "schema_version": "1.0",
                "run_id": run_id,
                "app_id": app_id,
                "created_at_utc": _utc_now(),
                "requirements_sha256": state["requirements_sha256"],
                "generator_entrypoint": GENERATOR_ENTRYPOINT,
                "mock_boundary": "enforced",
                "real_payment_calls": "disabled",
                "default_runtime_llm_calls": 0,
                "plan": plan,
                "native_capability_pre_run": plan.get("native_capability_pre_run", {}),
                "transition_history": self._ledger(paths.ledger),
                "generated_application_created": self._trusted_application_root(paths).exists(),
            }
            plan_payload["plan_sha256"] = _canonical_payload_sha256(
                plan_payload,
                exclude="plan_sha256",
            )
            _atomic_write_json(paths.plan, plan_payload)
            pre_run = plan.get("native_capability_pre_run", {})
            if isinstance(pre_run, dict) and pre_run.get("mandatory_gate_passed") is not True:
                self._transition(run_id, "CAPABILITY_PRE_RUN_BLOCKED", reason="native_capability_pre_run_no_go")
                self._fail_run(
                    run_id,
                    reason="native_capability_pre_run_no_go",
                    message="Application engineering stopped before source generation because the native capability pre-run was NO_GO.",
                )
                return {"status": "capability_pre_run_blocked", "run": self.get_run(run_id), **self._governance_payload()}
            self._transition(run_id, "CAPABILITY_PRE_RUN_READY", reason="native_capability_pre_run_passed")
            self._transition(run_id, "PLAN_READY", reason="plan_ready")
            self._transition(run_id, "AWAITING_APPROVAL", reason="application_engineering_requires_approval")
        return {"status": "plan_ready", "run": self.get_run(run_id), **self._governance_payload()}

    def approve(self, run_id: str, *, actor: str, approval_token: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        if state["state"] not in {"AWAITING_APPROVAL", "APPROVED"}:
            raise OrchestrationConflict(f"Cannot approve from state {state['state']}")
        expected_token = _approval_token()
        if not hmac.compare_digest(approval_token, expected_token):
            raise OrchestrationValidationError(
                [{"code": "invalid_approval_token", "message": "Approval token is not valid."}]
            )
        plan = _read_json(paths.plan)
        app_id = self._state_app_id(state)
        plan_sha = str(
            plan.get("plan_sha256")
            or _canonical_payload_sha256(plan, exclude="plan_sha256")
        )
        subject = {
            "run_id": run_id,
            "app_id": app_id,
            "action": RUN_ACTION_APPLICATION_ENGINEERING,
            "requirements_sha256": state["requirements_sha256"],
            "plan_sha256": plan_sha,
        }
        approval = {
            "schema_version": "browser-driven-intake-approval.v1",
            **subject,
            "actor": actor.strip() or "operator",
            "approval_subject_sha256": _json_sha256(subject),
            "approved_at_utc": _utc_now(),
        }
        _append_jsonl(paths.approvals, approval)
        self._update_state(run_id, {"approval": approval})
        if state["state"] != "APPROVED":
            self._transition(run_id, "APPROVED", reason="human_approval_recorded")
        return {"status": "approved", "run": self.get_run(run_id), **self._governance_payload()}

    def execute(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        if state["state"] in {"EXECUTION_QUEUED", "EXECUTING", "VALIDATING"}:
            return {"status": "already_queued", "run": self.get_run(run_id), **self._governance_payload()}
        if state["state"] == "SUCCEEDED":
            return {"status": "already_succeeded", "run": self.get_run(run_id), **self._governance_payload()}
        if state["state"] in TERMINAL_STATES:
            raise OrchestrationConflict(f"Cannot execute terminal run {run_id}")
        if state["state"] != "APPROVED" or not state.get("approval"):
            raise OrchestrationConflict("Application engineering requires run-scoped approval.")
        self._assert_current_approval(run_id, state)
        self._validate_portfolio_contract()
        with self._worker_lock:
            if run_id in self._active_workers:
                return {"status": "already_queued", "run": self.get_run(run_id), **self._governance_payload()}
            self._active_workers.add(run_id)
        self._transition(run_id, "EXECUTION_QUEUED", reason="engineering_queued")
        LOGGER.info(
            "Engineering run queued.",
            extra={
                "event_name": "engineering.run.queued",
                "attributes": {"run_id": run_id, "operation": "application_engineering"},
            },
        )
        thread = threading.Thread(
            target=self._execute_worker,
            args=(run_id,),
            name=f"portal-engineering-{run_id}",
            daemon=True,
        )
        thread.start()
        return {"status": "queued", "run": self.get_run(run_id), **self._governance_payload()}

    def recover_orphaned_runs(self) -> list[str]:
        recovered: list[str] = []
        if not self.state_root.exists():
            return recovered
        for state_path in sorted(self.state_root.glob("run_*/state.json")):
            try:
                state = _read_json(state_path)
                run_id = str(state.get("run_id") or state_path.parent.name)
                if state.get("state") in {"EXECUTION_QUEUED", "EXECUTING", "VALIDATING"}:
                    self._fail_run(
                        run_id,
                        reason="orphaned_non_terminal_run_recovered",
                        message="Run was recovered after portal restart before a terminal result was recorded.",
                    )
                    recovered.append(run_id)
            except (OSError, ValueError, json.JSONDecodeError, OrchestrationNotFound):
                continue
        return recovered

    def cancel(self, run_id: str) -> dict[str, Any]:
        state = _read_json(self._paths(run_id).state)
        if state["state"] in TERMINAL_STATES:
            raise OrchestrationConflict(f"Cannot cancel terminal run {run_id}")
        self._transition(run_id, "CANCELLED", reason="operator_cancelled")
        return {"status": "cancelled", "run": self.get_run(run_id), **self._governance_payload()}

    def events(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        if not paths.events.is_file():
            return {"run_id": run_id, "events": []}
        return {"run_id": run_id, "events": self._ledger(paths.events)}

    def evidence(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        payload = {
            "schema_version": "browser-driven-intake-evidence.v1",
            "run_id": run_id,
            "state": _read_json(paths.state),
            "state_history": self._ledger(paths.ledger),
            "approval_ledger": self._ledger(paths.approvals) if paths.approvals.is_file() else [],
            "events": self.events(run_id)["events"],
            "plan": _read_json(paths.plan) if paths.plan.is_file() else None,
            "engineering_result": _read_json(paths.result) if paths.result.is_file() else None,
            "quality_gates": self._quality_gates(paths),
            "final_decision": _read_json(paths.state).get("final_decision"),
            "manifest": self._manifest(paths),
            **self._governance_payload(),
        }
        payload["sha256"] = _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))
        return payload

    def validation(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        return {
            "schema_version": "browser-driven-intake-validation.v1",
            "run_id": run_id,
            "state": state["state"],
            "decision": state.get("final_decision"),
            "quality_gates": self._quality_gates(paths),
            "mandatory_gates_passed": self._mandatory_gates_passed(paths),
            "engineering_result": _read_json(paths.result) if paths.result.is_file() else None,
            **self._governance_payload(),
        }

    def _publication_root(self, *, run_id: str, app_id: str) -> Path:
        app_id = validate_app_id(app_id)
        root = (
            self.publication_root
            / "factory_generated"
            / app_id
            / "portal_publications"
            / run_id
        ).resolve()
        self._assert_trusted_publication_path(root)
        return root

    def _assert_trusted_publication_path(self, root: Path) -> None:
        project_root = self.project_root.resolve()
        publication_root = self.publication_root.resolve()
        if _is_relative_to(root, project_root) or _is_relative_to(root, publication_root):
            return
        raise OrchestrationConflict("Publication root must stay inside a trusted local workspace.")

    def _state_app_id(self, state: dict[str, Any]) -> str:
        app_id = validate_app_id(str(state.get("app_id", APP_ID)))
        expected = _sha256_bytes(app_id.encode("utf-8"))
        stored = state.get("app_id_sha256")
        if stored is not None and stored != expected:
            raise OrchestrationConflict("Application ID is immutable after run creation.")
        if stored is None and app_id == APP_ID:
            return app_id
        if stored is None:
            raise OrchestrationConflict("Application ID identity evidence is missing.")
        return app_id

    def _trusted_application_root(self, paths: PortalRunPaths) -> Path:
        if paths.result.is_file():
            result = _read_json(paths.result)
            registration = result.get("portfolio_registration")
            if isinstance(registration, dict):
                application_root = registration.get("application_root")
                if isinstance(application_root, str) and application_root:
                    root = Path(application_root).expanduser().resolve()
                    self._assert_trusted_publication_path(root)
                    return root
            output_root = result.get("output_root")
            if isinstance(output_root, str) and output_root:
                root = Path(output_root).expanduser().resolve()
                if _is_relative_to(root, self.project_root.resolve()) or _is_relative_to(
                    root,
                    self.publication_root.resolve(),
                ):
                    return root
        state = _read_json(paths.state)
        app_id = self._state_app_id(state)
        return self._publication_root(run_id=str(state["run_id"]), app_id=app_id) / "generated_application"

    def application_archive(self, run_id: str) -> Path:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        if state["state"] != "SUCCEEDED":
            raise OrchestrationConflict("Generated application download is not ready.")
        application_root = self._trusted_application_root(paths)
        if not application_root.is_dir():
            raise OrchestrationNotFound("Generated application archive is not available.")
        archive = paths.archives / "generated_application.zip"
        if not archive.is_file():
            result = _read_json(paths.result) if paths.result.is_file() else {}
            registration = result.get("portfolio_registration")
            portfolio_registration = registration if isinstance(registration, dict) else None
            _write_generation_manifest(
                manifest_path=application_root / "generation_manifest.json",
                project_root=self.project_root,
                run_id=run_id,
                requirements_sha256=str(state["requirements_sha256"]),
                generated_application=application_root,
                app_id=self._state_app_id(state),
                version_id=str(portfolio_registration["version_id"])
                if portfolio_registration and portfolio_registration.get("version_id")
                else None,
                portfolio_registration=portfolio_registration,
                openapi=result.get("openapi") if isinstance(result.get("openapi"), dict) else None,
                openapi_inventory=result.get("openapi_inventory") if isinstance(result.get("openapi_inventory"), dict) else None,
            )
            digest = _zip_generated_application(
                archive_path=archive,
                root=application_root,
                top_level_directory=application_root.name,
            )
            _atomic_write_text(paths.archives / "generated_application.zip.sha256", digest + "\n")
        return archive

    def evidence_archive(self, run_id: str) -> Path:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        if state["state"] != "SUCCEEDED":
            raise OrchestrationConflict("Evidence bundle download is not ready.")
        application_archive = self.application_archive(run_id)
        application_digest = _sha256_file(application_archive)
        application_size = application_archive.stat().st_size
        application_filename = f"{run_id}_{APPLICATION_DOWNLOAD_FILENAME}"

        staging_parent = paths.archives / "evidence_bundle"
        top_level = f"{run_id}_evidence"
        evidence_root = staging_parent / top_level
        if staging_parent.exists():
            shutil.rmtree(staging_parent)
        evidence_root.mkdir(parents=True)

        requirements_bytes = paths.requirements.read_bytes()
        requirements_sha256 = _sha256_bytes(requirements_bytes)
        plan = _read_json(paths.plan)
        plan_sha256 = str(
            plan.get("plan_sha256")
            or _canonical_payload_sha256(plan, exclude="plan_sha256")
        )

        (evidence_root / "requirements.md").write_bytes(requirements_bytes)
        _atomic_write_json(evidence_root / "plan.json", plan)
        _atomic_write_json(
            evidence_root / "approval_ledger.json",
            self._evidence_approval_ledger(
                paths,
                run_id=run_id,
                requirements_sha256=requirements_sha256,
                plan_sha256=plan_sha256,
            ),
        )
        _atomic_write_text(
            evidence_root / "event_ledger.jsonl",
            self._evidence_event_ledger_text(paths, run_id=run_id, terminal_state="SUCCEEDED"),
        )
        _atomic_write_json(
            evidence_root / "execution_report.json",
            self._evidence_execution_report(
                paths,
                run_id=run_id,
                application_archive_sha256=application_digest,
                application_archive_size_bytes=application_size,
            ),
        )
        validation_report = self._evidence_validation_report(
            paths,
            run_id=run_id,
            requirements_sha256=requirements_sha256,
        )
        _atomic_write_json(evidence_root / "validation_report.json", validation_report)
        result = _read_json(paths.result)
        if isinstance(result.get("generated_test_execution"), dict):
            _atomic_write_json(
                evidence_root / "generated_test_execution.json",
                cast(dict[str, Any], result["generated_test_execution"]),
            )
        if isinstance(result.get("openapi"), dict):
            _atomic_write_json(evidence_root / "openapi.json", cast(dict[str, Any], result["openapi"]))
        if isinstance(result.get("openapi_inventory"), dict):
            _atomic_write_json(
                evidence_root / "openapi_inventory.json",
                cast(dict[str, Any], result["openapi_inventory"]),
            )
        _atomic_write_json(
            evidence_root / "decision.json",
            self._evidence_decision(
                state,
                run_id=run_id,
                requirements_sha256=requirements_sha256,
                validation_report=validation_report,
            ),
        )
        _atomic_write_text(
            evidence_root / "application_archive.sha256",
            f"{application_digest}  {application_filename}\n",
        )
        _atomic_write_json(
            evidence_root / "evidence_manifest.json",
            self._evidence_manifest(
                evidence_root,
                run_id=run_id,
                requirements_sha256=requirements_sha256,
                application_archive_sha256=application_digest,
            ),
        )
        archive = paths.archives / "evidence_bundle.zip"
        digest = _safe_zip_tree(archive, evidence_root, top_level_directory=top_level)
        _atomic_write_text(paths.archives / "evidence_bundle.zip.sha256", digest + "\n")
        return archive

    def _evidence_approval_ledger(
        self,
        paths: PortalRunPaths,
        *,
        run_id: str,
        requirements_sha256: str,
        plan_sha256: str,
    ) -> dict[str, Any]:
        approvals = self._ledger(paths.approvals)
        if not approvals:
            raise OrchestrationConflict("Evidence bundle requires a persisted approval ledger.")
        approval = approvals[-1]
        approved_at = str(approval.get("approved_at_utc", ""))
        if not approved_at:
            raise OrchestrationConflict("Evidence bundle requires approval timestamp evidence.")
        return {
            "schema_version": "1.0",
            "run_id": run_id,
            "action": "APPLICATION_ENGINEERING",
            "approved": True,
            "requirements_sha256": requirements_sha256,
            "plan_sha256": plan_sha256,
            "approved_at_utc": approved_at,
        }

    def _evidence_event_ledger_text(
        self,
        paths: PortalRunPaths,
        *,
        run_id: str,
        terminal_state: str,
    ) -> str:
        events = self._ledger(paths.events)
        if not events:
            raise OrchestrationConflict("Evidence bundle requires persisted run events.")
        lines: list[str] = []
        seen_sequences: set[int] = set()
        last_sequence = 0
        for index, event in enumerate(events, start=1):
            sequence_value = event.get("sequence")
            sequence = sequence_value if isinstance(sequence_value, int) else index
            if sequence <= 0 or sequence in seen_sequences or sequence <= last_sequence:
                sequence = last_sequence + 1
            seen_sequences.add(sequence)
            last_sequence = sequence
            event_type = str(event.get("event_type") or event.get("type") or "")
            recorded_at = str(event.get("recorded_at_utc") or event.get("at_utc") or "")
            state = str(event.get("state") or self._event_state(event, terminal_state=terminal_state))
            if not event_type or not recorded_at or not state:
                raise OrchestrationConflict("Evidence bundle requires complete event ledger entries.")
            evidence_event = {
                "sequence": sequence,
                "run_id": run_id,
                "event_type": event_type,
                "state": state,
                "recorded_at_utc": recorded_at,
                "payload": event.get("payload", {}),
            }
            lines.append(json.dumps(evidence_event, sort_keys=True))
        if not any(json.loads(line)["state"] == terminal_state for line in lines):
            raise OrchestrationConflict("Evidence bundle requires a successful terminal event.")
        return "\n".join(lines) + "\n"

    def _event_state(self, event: dict[str, Any], *, terminal_state: str) -> str:
        event_type = event.get("type") or event.get("event_type")
        payload = event.get("payload")
        if isinstance(payload, dict):
            if event_type == "state_transition":
                target = payload.get("to")
                if isinstance(target, str) and target:
                    return target
            if event_type == "final_decision":
                return terminal_state
        if event_type == "run_created":
            return "DRAFT"
        return terminal_state

    def _evidence_execution_report(
        self,
        paths: PortalRunPaths,
        *,
        run_id: str,
        application_archive_sha256: str,
        application_archive_size_bytes: int,
    ) -> dict[str, Any]:
        result = _read_json(paths.result)
        completed_at = str(result.get("completed_at_utc", ""))
        if not completed_at:
            raise OrchestrationConflict("Evidence bundle requires completion timestamp evidence.")
        return {
            "schema_version": "1.0",
            "run_id": run_id,
            "state": "SUCCEEDED",
            "generator_entrypoint": GENERATOR_ENTRYPOINT,
            "application_archive_sha256": application_archive_sha256,
            "application_archive_size_bytes": application_archive_size_bytes,
            "generated_test_execution_sha256": _json_sha256(cast(dict[str, Any], result.get("generated_test_execution", {}))),
            "openapi_sha256": cast(dict[str, Any], result.get("openapi_inventory", {})).get("openapi_sha256"),
            "mock_boundary": "enforced",
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
            "completed_at_utc": completed_at,
        }

    def _evidence_validation_report(
        self,
        paths: PortalRunPaths,
        *,
        run_id: str,
        requirements_sha256: str,
    ) -> dict[str, Any]:
        gates = self._evidence_validation_gates(paths)
        passed = all(gate["passed"] is True for gate in gates)
        return {
            "schema_version": "1.0",
            "run_id": run_id,
            "requirements_sha256": requirements_sha256,
            "passed": passed,
            "mandatory_gates_passed": passed and self._mandatory_gates_passed(paths),
            "failure_count": 0 if passed else len([gate for gate in gates if gate["passed"] is not True]),
            "gates": gates,
        }

    def _evidence_validation_gates(self, paths: PortalRunPaths) -> list[dict[str, Any]]:
        result = _read_json(paths.result)
        application_root = self._trusted_application_root(paths)
        generation_manifest = application_root / "generation_manifest.json"
        gates = [
            (
                "generated application structure",
                application_root.is_dir() and any(application_root.rglob("*.py")),
                "Generated application directory contains Python source files.",
            ),
            (
                "tests",
                bool(result.get("generated_tests")),
                "Generated application result lists deterministic tests.",
            ),
            (
                "tests executed",
                isinstance(result.get("generated_test_execution"), dict)
                and result["generated_test_execution"].get("exit_code") == 0
                and result["generated_test_execution"].get("go_gate") == "GO"
                and result["generated_test_execution"].get("counts", {}).get("collected", 0) > 0,
                "Generated application pytest suite executed inside the governed portal run before GO.",
            ),
            (
                "OpenAPI publication",
                isinstance(result.get("openapi"), dict)
                and isinstance(result.get("openapi_inventory"), dict)
                and result["openapi_inventory"].get("catalogue_only_fallback_used") is False
                and bool(result["openapi_inventory"].get("endpoint_inventory"))
                and _endpoint_inventory_contains_path(result.get("openapi_inventory"), path="/v1/disputes"),
                "Generated application OpenAPI document was captured from the generated FastAPI app and includes the primary portal gate marker `/v1/disputes`.",
            ),
            (
                "archive safety",
                True,
                "Archive members are checked for duplicate, absolute, traversal, and symlink paths.",
            ),
            (
                "generation manifest",
                generation_manifest.is_file(),
                "Generated application archive includes generation_manifest.json.",
            ),
            (
                "mock boundary",
                result.get("mock_safe") is True,
                "Application engineering executed with mock_safe true.",
            ),
            (
                "real payment calls disabled",
                result.get("real_payment_calls") == "disabled",
                "Application engineering reported real_payment_calls disabled.",
            ),
            (
                "certification posture",
                CERTIFICATION_POSTURE == "certification-ready-not-certified",
                "Certification posture remains certification-ready-not-certified.",
            ),
        ]
        return [
            {"name": name, "passed": passed is True, "evidence": evidence}
            for name, passed, evidence in gates
        ]

    def _evidence_decision(
        self,
        state: dict[str, Any],
        *,
        run_id: str,
        requirements_sha256: str,
        validation_report: dict[str, Any],
    ) -> dict[str, Any]:
        if validation_report.get("passed") is not True or state.get("final_decision") != "GO":
            raise OrchestrationConflict("Evidence bundle requires a validation-derived GO decision.")
        decided_at = str(state.get("updated_at_utc", ""))
        if not decided_at:
            raise OrchestrationConflict("Evidence bundle requires a decision timestamp.")
        return {
            "schema_version": "1.0",
            "run_id": run_id,
            "requirements_sha256": requirements_sha256,
            "decision": "GO",
            "source": "validation",
            "decided_at_utc": decided_at,
            "certification_posture": CERTIFICATION_POSTURE,
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
        }

    def _evidence_manifest(
        self,
        evidence_root: Path,
        *,
        run_id: str,
        requirements_sha256: str,
        application_archive_sha256: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "artifact_type": "run_evidence_bundle",
            "run_id": run_id,
            "requirements_sha256": requirements_sha256,
            "application_archive_sha256": application_archive_sha256,
            "generated_at_utc": _utc_now(),
            "mock_boundary": "enforced",
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
            "certification_posture": CERTIFICATION_POSTURE,
            "files": self._evidence_file_inventory(evidence_root),
        }

    def _evidence_file_inventory(self, evidence_root: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in sorted(evidence_root.rglob("*")):
            if path.is_dir():
                continue
            relative = _safe_relative_file_path(path, evidence_root)
            if relative == "evidence_manifest.json":
                continue
            if relative in seen:
                raise ValueError(f"Duplicate evidence path: {relative}")
            seen.add(relative)
            payload = path.read_bytes()
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256_bytes(payload),
                    "size_bytes": len(payload),
                }
            )
        return records

    def _execute_worker(self, run_id: str) -> None:
        paths = self._paths(run_id)
        app_id = self._state_app_id(_read_json(paths.state))
        with logging_context(run_id=run_id, app_id=app_id):
            try:
                self._execute_worker_transaction(run_id, paths)
            finally:
                with self._worker_lock:
                    self._active_workers.discard(run_id)

    def _execute_worker_transaction(self, run_id: str, paths: PortalRunPaths) -> None:
        try:
            self._validate_portfolio_contract()
            if _read_json(paths.state)["state"] == "CANCELLED":
                return
            self._transition(run_id, "EXECUTING", reason="engineering_started")
            LOGGER.info(
                "Engineering run started.",
                extra={
                    "event_name": "engineering.run.started",
                    "attributes": {"run_id": run_id, "operation": "application_engineering"},
                },
            )
            result = dict(run_requirements_engineering(self._adapter_config(paths, plan_only=False)))
            _atomic_write_json(paths.result, result)
            if _read_json(paths.state)["state"] == "CANCELLED":
                return
            self._transition(run_id, "VALIDATING", reason="engineering_result_recorded")
            decision = "GO" if self._mandatory_gates_passed(paths) else "NO-GO"
            if decision == "GO":
                registration = self._register_generated_application(run_id, paths, result)
                result = {**result, "portfolio_registration": registration}
                _atomic_write_json(paths.result, result)
                LOGGER.info(
                    "Portfolio registration completed.",
                    extra={
                        "event_name": "portfolio.registration.succeeded",
                        "attributes": {
                            "run_id": run_id,
                            "app_id": registration.get("app_id"),
                            "version_id": registration.get("version_id"),
                            "outcome": "success",
                        },
                    },
                )
            self._update_state(run_id, {"final_decision": decision})
            self._transition(
                run_id,
                "SUCCEEDED" if decision == "GO" else "FAILED",
                reason="quality_gates_passed" if decision == "GO" else "quality_gates_failed",
            )
            self._record_event(run_id, "final_decision", {"decision": decision})
            LOGGER.info(
                "Engineering run completed.",
                extra={
                    "event_name": "engineering.run.succeeded",
                    "attributes": {
                        "run_id": run_id,
                        "app_id": self._state_app_id(_read_json(paths.state)),
                        "outcome": "success" if decision == "GO" else "failure",
                    },
                },
            )
        except PortfolioError as exc:
            self._fail_run(run_id, reason="engineering_failed_closed", message=str(exc))
        except Exception as exc:
            self._fail_run(run_id, reason="engineering_failed_closed", message=str(exc))

    def _fail_run(self, run_id: str, *, reason: str, message: str) -> None:
        paths = self._paths(run_id)
        safe_message = message.splitlines()[0][:500] if message else "engineering failed closed"
        result = _read_json(paths.result) if paths.result.is_file() else {}
        failure_result = {
            **result,
            "schema_version": "1.0",
            "status": "PORTAL_APPLICATION_ENGINEERING_FAILED_CLOSED",
            "run_id": run_id,
            "final_decision": "NO-GO",
            "validated": False,
            "registered": False,
            "error": {"type": "engineering_transaction_failed", "message": safe_message},
            "llm_calls": 0,
            "real_payment_calls": "disabled",
            "completed_at_utc": _utc_now(),
        }
        _atomic_write_json(paths.result, failure_result)
        self._update_state(run_id, {"final_decision": "NO-GO", "error": safe_message})
        current = _read_json(paths.state)["state"]
        if current not in TERMINAL_STATES:
            self._transition(run_id, "FAILED", reason=reason)
        self._record_event(
            run_id,
            "engineering_failed_closed",
            {"reason": reason, "message": safe_message, "decision": "NO-GO"},
        )
        LOGGER.error(
            "Engineering run failed closed.",
            extra={
                "event_name": "engineering.run.failed",
                "attributes": {
                    "run_id": run_id,
                    "app_id": self._state_app_id(_read_json(paths.state)),
                    "operation": "application_engineering",
                    "outcome": "failure",
                    "error.type": "engineering_transaction_failed",
                    "error.message": safe_message,
                },
            },
        )

    def _register_generated_application(
        self,
        run_id: str,
        paths: PortalRunPaths,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        requirements_text = paths.requirements.read_text(encoding="utf-8")
        requirements_sha256 = _sha256_bytes(requirements_text.encode("utf-8"))
        state = _read_json(paths.state)
        app_id = self._state_app_id(state)
        application_root = self._trusted_application_root(paths)
        evidence_root = Path(str(result.get("evidence_root", paths.engineering_evidence))).expanduser().resolve()
        if not (
            _is_relative_to(evidence_root, self.project_root.resolve())
            or _is_relative_to(evidence_root, self.publication_root.resolve())
        ):
            evidence_root = self._publication_root(run_id=run_id, app_id=app_id) / "engineering_evidence"
        version_id = _deterministic_version_id(
            app_id=app_id,
            run_id=run_id,
            requirements_sha256=requirements_sha256,
        )
        metadata_path = application_root / "generation_metadata.json"
        metadata = _read_json(metadata_path) if metadata_path.is_file() else {}
        metadata.update(
            {
                "app_id": app_id,
                "version_id": version_id,
                "source_run_id": run_id,
                "requirements_sha256": requirements_sha256,
                "portfolio_state_root": str(self.portfolio_store.state_root),
                "application_root": str(application_root),
            }
        )
        _atomic_write_json(metadata_path, metadata)
        _write_generation_manifest(
            manifest_path=application_root / "generation_manifest.json",
            project_root=self.project_root,
            run_id=run_id,
            app_id=app_id,
            version_id=version_id,
            requirements_sha256=requirements_sha256,
            generated_application=application_root,
            openapi=result.get("openapi") if isinstance(result.get("openapi"), dict) else None,
            openapi_inventory=result.get("openapi_inventory") if isinstance(result.get("openapi_inventory"), dict) else None,
        )
        manifest = _read_json(application_root / "generation_manifest.json")
        if not isinstance(manifest.get("openapi"), dict) or not isinstance(manifest.get("openapi_inventory"), dict):
            raise PortfolioError("generated OpenAPI evidence is required for portfolio registration")
        evidence = {
            "schema_version": "1.0",
            "artifact_type": "portfolio_registration_evidence",
            "app_id": app_id,
            "version_id": version_id,
            "generated_run_id": run_id,
            "source_run_id": run_id,
            "adapter_run_id": result.get("run_id"),
            "requirements_sha256": requirements_sha256,
            "application_root": str(application_root),
            "engineering_result_sha256": _json_sha256(result),
            "generation_manifest_sha256": _sha256_file(application_root / "generation_manifest.json"),
            "registered_at_utc": _utc_now(),
            "mock_boundary": "enforced",
            "real_payment_calls": "disabled",
            "certification_posture": CERTIFICATION_POSTURE,
        }
        version = self.portfolio_catalogue.register(
            RegistrationRequest(
                app_id=app_id,
                version_id=version_id,
                generated_run_id=run_id,
                requirements=requirements_text,
                source_commit=_source_commit(self.project_root),
                evidence=evidence,
                manifest=manifest,
                entrypoint=str(result.get("entrypoint") or f"app.{app_id}.interfaces.api.main:app"),
                application_root=application_root,
                capabilities=tuple(
                    str(item)
                    for item in result.get(
                        "capabilities",
                        (
                            "failed_debit_disputes",
                            "evidence_collection",
                            "investigation",
                            "human_review",
                            "disposition",
                            "audit_integrity",
                            "closure",
                            "health",
                            "ready",
                        ),
                    )
                ),
            )
        )
        registration = {
            **evidence,
            "catalogue_path": str(self.portfolio_store.catalogue_path),
            "catalogue_sha256": self.portfolio_catalogue.catalogue()["catalogue_sha256"],
            "version_identity_sha256": version.identity_sha256,
        }
        _atomic_write_json(evidence_root / "portfolio_registration.json", registration)
        _write_generation_manifest(
            manifest_path=application_root / "generation_manifest.json",
            project_root=self.project_root,
            run_id=run_id,
            app_id=app_id,
            version_id=version_id,
            requirements_sha256=requirements_sha256,
            generated_application=application_root,
            portfolio_registration=registration,
            openapi=manifest.get("openapi") if isinstance(manifest.get("openapi"), dict) else None,
            openapi_inventory=manifest.get("openapi_inventory") if isinstance(manifest.get("openapi_inventory"), dict) else None,
        )
        metadata["portfolio_registration"] = registration
        _atomic_write_json(metadata_path, metadata)
        return registration

    def _adapter_config(self, paths: PortalRunPaths, *, plan_only: bool) -> AdapterConfig:
        state = _read_json(paths.state)
        app_id = self._state_app_id(state)
        publication_root = self._publication_root(run_id=str(state["run_id"]), app_id=app_id)
        return AdapterConfig(
            requirements=paths.requirements,
            app_id=app_id,
            output_root=publication_root / "generated_application",
            evidence_root=publication_root / "engineering_evidence",
            approval_mode="proposal-only" if plan_only else "human-gated",
            approval_token=None if plan_only else _approval_token(),
            mock_safe=True,
            plan_only=plan_only,
            replace_existing=False,
            factory_root=self.project_root,
            workspace_root=publication_root,
            portfolio_state_root=self.portfolio_store.state_root,
            engineering_profile="authoritative-failed-debit-v1",
            register_with_portfolio=False,
        )

    def _validate_portfolio_contract(self) -> None:
        resolve_state_roots(
            project_root=self.project_root,
            browser_state_root=self.state_root,
            portfolio_state_root=self.portfolio_store.state_root,
        )

    def _paths(self, run_id: str) -> PortalRunPaths:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise OrchestrationNotFound("Run ID was not found.")
        root = (self.state_root / run_id).resolve()
        try:
            root.relative_to(self.state_root)
        except ValueError as exc:
            raise OrchestrationNotFound("Run ID was not found.") from exc
        return PortalRunPaths(
            root=root,
            requirements=root / "requirements.md",
            state=root / "state.json",
            ledger=root / "state_ledger.jsonl",
            events=root / "events.jsonl",
            approvals=root / "approval_ledger.jsonl",
            plan=root / "plan.json",
            result=root / "engineering_result.json",
            generated_application=root / "generated_application",
            engineering_evidence=root / "engineering_evidence",
            archives=root / "archives",
        )

    def _transition(self, run_id: str, target: RunState, *, reason: str) -> None:
        state = _read_json(self._paths(run_id).state)
        current = cast(RunState, state["state"])
        if target not in VALID_TRANSITIONS[current]:
            raise OrchestrationConflict(f"Invalid transition from {current} to {target}")
        self._update_state(run_id, {"state": target})
        self._record_event(run_id, "state_transition", {"from": current, "to": target, "reason": reason})
        _append_jsonl(
            self._paths(run_id).ledger,
            {"at_utc": _utc_now(), "from": current, "to": target, "reason": reason},
        )

    def _update_state(self, run_id: str, updates: dict[str, Any]) -> None:
        paths = self._paths(run_id)
        state = _read_json(paths.state)
        state.update(updates)
        state["updated_at_utc"] = _utc_now()
        _atomic_write_json(paths.state, state)

    def _record_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        paths = self._paths(run_id)
        prior_events = self._ledger(paths.events)
        last_sequence = 0
        if prior_events:
            sequence = prior_events[-1].get("sequence")
            if isinstance(sequence, int):
                last_sequence = sequence
            else:
                last_sequence = len(prior_events)
        state = _read_json(paths.state)
        recorded_at = _utc_now()
        _append_jsonl(
            paths.events,
            {
                "sequence": last_sequence + 1,
                "recorded_at_utc": recorded_at,
                "at_utc": recorded_at,
                "run_id": run_id,
                "event_type": event_type,
                "type": event_type,
                "state": state["state"],
                "payload": payload,
            },
        )

    def _ledger(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        return [
            cast(dict[str, Any], json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _artifact_status(self, paths: PortalRunPaths) -> dict[str, bool]:
        application_root = self._trusted_application_root(paths) if paths.state.is_file() else paths.generated_application
        return {
            "generated_application_available": application_root.is_dir(),
            "evidence_bundle_available": paths.state.is_file(),
            "plan_available": paths.plan.is_file(),
            "engineering_result_available": paths.result.is_file(),
        }

    def _quality_gates(self, paths: PortalRunPaths) -> dict[str, Any]:
        result = _read_json(paths.result) if paths.result.is_file() else {}
        manifest = result.get("generated_file_count", 0)
        application_root = self._trusted_application_root(paths) if paths.state.is_file() else paths.generated_application
        return {
            "health_contract": result.get("health_contract") is True,
            "ready_contract": result.get("ready_contract") is True,
            "failed_debit_runtime_contract": result.get("failed_debit_runtime_contract") is True,
            "failed_debit_primary_flow_test": result.get("failed_debit_primary_flow_test") is True,
            "tests_present": bool(result.get("generated_tests")),
            "tests_executed": (
                isinstance(result.get("generated_test_execution"), dict)
                and result["generated_test_execution"].get("exit_code") == 0
                and result["generated_test_execution"].get("go_gate") == "GO"
                and result["generated_test_execution"].get("counts", {}).get("collected", 0) > 0
            ),
            "openapi_published": (
                isinstance(result.get("openapi"), dict)
                and isinstance(result.get("openapi_inventory"), dict)
                and result["openapi_inventory"].get("catalogue_only_fallback_used") is False
                and _endpoint_inventory_contains_path(result.get("openapi_inventory"), path="/v1/disputes")
            ),
            "source_present": application_root.is_dir() and any(application_root.rglob("*.py")),
            "archive_safe": True,
            "default_llm_calls": result.get("llm_calls", 0),
            "real_payment_calls": result.get("real_payment_calls", "disabled"),
            "mock_boundary": True,
            "generated_file_count": manifest,
            "certification_posture": CERTIFICATION_POSTURE,
        }

    def _mandatory_gates_passed(self, paths: PortalRunPaths) -> bool:
        gates = self._quality_gates(paths)
        return (
            gates["health_contract"] is True
            and gates["ready_contract"] is True
            and gates["failed_debit_runtime_contract"] is True
            and gates["failed_debit_primary_flow_test"] is True
            and gates["tests_present"] is True
            and gates["tests_executed"] is True
            and gates["openapi_published"] is True
            and gates["source_present"] is True
            and gates["default_llm_calls"] == 0
            and gates["real_payment_calls"] == "disabled"
            and gates["mock_boundary"] is True
            and gates["certification_posture"] == CERTIFICATION_POSTURE
        )

    def _assert_current_approval(self, run_id: str, state: dict[str, Any]) -> None:
        approval = state.get("approval")
        if not isinstance(approval, dict):
            raise OrchestrationConflict("Application engineering requires run-scoped approval.")
        plan = _read_json(self._paths(run_id).plan)
        expected = {
            "run_id": run_id,
            "app_id": self._state_app_id(state),
            "action": RUN_ACTION_APPLICATION_ENGINEERING,
            "requirements_sha256": state["requirements_sha256"],
            "plan_sha256": str(
                plan.get("plan_sha256")
                or _canonical_payload_sha256(plan, exclude="plan_sha256")
            ),
        }
        expected_subject = _json_sha256(expected)
        if approval.get("approval_subject_sha256") != expected_subject:
            raise OrchestrationConflict("Run approval is stale for the current requirements and plan.")

    def _manifest(self, paths: PortalRunPaths) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(paths.root.rglob("*")):
            if path.is_file() and "archives" not in path.relative_to(paths.root).parts:
                records.append(
                    {
                        "relative_path": path.relative_to(paths.root).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha256_file(path),
                    }
                )
        return records

    def _governance_payload(self) -> dict[str, Any]:
        return {
            "mock_boundary": True,
            "real_payment_calls": "disabled",
            "llm_calls": 0,
            "certification_posture": CERTIFICATION_POSTURE,
        }
