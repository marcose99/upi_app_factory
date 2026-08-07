from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError


GENERATED_APP_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_PARENT = GENERATED_APP_ROOT.parent

if str(GENERATED_APP_PARENT) not in sys.path:
    sys.path.insert(0, str(GENERATED_APP_PARENT))


WORKSPACE_PACKAGE_PATHS: tuple[tuple[str, Path], ...] = (
    ("generated_application", GENERATED_APP_ROOT),
    ("generated_application.app", GENERATED_APP_ROOT / "app"),
    ("generated_application.app.application", GENERATED_APP_ROOT / "app/application"),
    ("generated_application.app.domain", GENERATED_APP_ROOT / "app/domain"),
    ("generated_application.app.infrastructure", GENERATED_APP_ROOT / "app/infrastructure"),
    (
        "generated_application.app.infrastructure.persistence",
        GENERATED_APP_ROOT / "app/infrastructure/persistence",
    ),
    ("generated_application.app.interfaces", GENERATED_APP_ROOT / "app/interfaces"),
    ("generated_application.app.interfaces.api", GENERATED_APP_ROOT / "app/interfaces/api"),
    ("generated_application.app.security", GENERATED_APP_ROOT / "app/security"),
)

WORKSPACE_RUNTIME_MODULES: tuple[tuple[str, Path], ...] = (
    ("generated_application.app.domain.value_objects", GENERATED_APP_ROOT / "app/domain/value_objects.py"),
    ("generated_application.app.domain.exceptions", GENERATED_APP_ROOT / "app/domain/exceptions.py"),
    ("generated_application.app.domain.domain_events", GENERATED_APP_ROOT / "app/domain/domain_events.py"),
    ("generated_application.app.domain.policies", GENERATED_APP_ROOT / "app/domain/policies.py"),
    ("generated_application.app.domain.entities", GENERATED_APP_ROOT / "app/domain/entities.py"),
    ("generated_application.app.security.pii_redaction", GENERATED_APP_ROOT / "app/security/pii_redaction.py"),
    ("generated_application.app.security.identity", GENERATED_APP_ROOT / "app/security/identity.py"),
    ("generated_application.app.application.commands", GENERATED_APP_ROOT / "app/application/commands.py"),
    ("generated_application.app.application.ports", GENERATED_APP_ROOT / "app/application/ports.py"),
    ("generated_application.app.application.unit_of_work", GENERATED_APP_ROOT / "app/application/unit_of_work.py"),
    (
        "generated_application.app.infrastructure.persistence.migrations",
        GENERATED_APP_ROOT / "app/infrastructure/persistence/migrations.py",
    ),
    (
        "generated_application.app.infrastructure.persistence.repositories",
        GENERATED_APP_ROOT / "app/infrastructure/persistence/repositories.py",
    ),
    (
        "generated_application.app.infrastructure.persistence.sqlite_unit_of_work",
        GENERATED_APP_ROOT / "app/infrastructure/persistence/sqlite_unit_of_work.py",
    ),
    ("generated_application.app.application.services", GENERATED_APP_ROOT / "app/application/services.py"),
    ("generated_application.app.interfaces.api.schemas", GENERATED_APP_ROOT / "app/interfaces/api/schemas.py"),
    (
        "generated_application.app.interfaces.api.error_handlers",
        GENERATED_APP_ROOT / "app/interfaces/api/error_handlers.py",
    ),
)


def _ensure_workspace_package(module_name: str, package_path: Path) -> None:
    preferred = str(package_path)
    existing = sys.modules.get(module_name)
    if existing is None:
        created = ModuleType(module_name)
        created.__package__ = module_name
        created.__path__ = [preferred]
        sys.modules[module_name] = created
        return
    module_path = getattr(existing, "__path__", None)
    if module_path is None:
        return
    ordered = [preferred]
    ordered.extend(str(entry) for entry in module_path if str(entry) != preferred)
    existing.__path__ = ordered


def _load_workspace_module(module_name: str, module_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load workspace runtime module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


def _prime_workspace_generated_runtime() -> None:
    importlib.invalidate_caches()
    for module_name, package_path in WORKSPACE_PACKAGE_PATHS:
        _ensure_workspace_package(module_name, package_path)
    for module_name, module_path in WORKSPACE_RUNTIME_MODULES:
        _load_workspace_module(module_name, module_path)


def _strip_hardened_facade_legacy_routes(app: FastAPI) -> FastAPI:
    app.router.routes = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) not in {"/runtime/health"}
    ]
    app.openapi_schema = None
    return app


def _hardened_api_app(*, database_path: Path | None = None) -> FastAPI:
    if database_path is not None:
        os.environ["UPI_DISPUTE_SQLITE_PATH"] = str(database_path)
    _prime_workspace_generated_runtime()
    module_name = "generated_application.app.interfaces.api.main"
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    return _strip_hardened_facade_legacy_routes(cast(FastAPI, module.app))


def _legacy_injection_app(
    *,
    repository: Any,
    audit_logger: Any,
    ecosystem: Any | None = None,
    settings: Any | None = None,
) -> FastAPI:
    from .cqrs import GetDisputeQuery, ListDisputesQuery, RunMockEcosystemCheckCommand
    from .cqrs import SubmitDisputeCommand
    from .domain_events import (
        DomainEventCollector,
        dispute_created_event,
        mock_ecosystem_checked_event,
    )
    from .errors import AppErrorCode, ApplicationError
    from .mock_ecosystem import MockEcosystemGateway
    from .models import (
        DisputeCreate,
        DisputeRecord,
        DisputeResponse,
        EcosystemCheckResult,
        new_id,
        utc_now_iso,
    )
    from .pii import assert_no_obvious_real_sensitive_values, mask_upi_id
    from .repository import (
        DisputeNotFoundError,
        DuplicateBusinessSubmissionError,
        DuplicateClientRequestError,
    )
    from .runtime import (
        build_runtime_state,
        configure_structured_logging,
        log_runtime_event,
        payload_fingerprint,
    )
    from .settings import RuntimeSettings
    from .unit_of_work import LocalSqliteUnitOfWork
    from .workflow import BOUNDARY_NOTICE, initial_status, next_actions_for
    from .workflow import status_from_ecosystem_decision

    def build_dispute_record(command: SubmitDisputeCommand) -> DisputeRecord:
        now = utc_now_iso()
        return DisputeRecord(
            dispute_id=new_id("disp"),
            client_request_id=command.client_request_id,
            dispute_type=command.dispute_type,
            transaction_reference=command.transaction_reference,
            masked_customer_upi_id=mask_upi_id(command.customer_upi_id),
            amount_paise=command.amount_paise,
            description=command.description,
            evidence=command.evidence,
            status=initial_status(command.dispute_type),
            created_at_utc=now,
            updated_at_utc=now,
            domain_notes=["Initial local dispute simulation record created."],
        )

    def business_duplicate_fingerprint(command: SubmitDisputeCommand) -> str:
        return cast(
            str,
            payload_fingerprint(
                {
                    "dispute_type": command.dispute_type.value,
                    "transaction_reference": command.transaction_reference,
                    "customer_upi_id": command.customer_upi_id,
                    "amount_paise": command.amount_paise,
                    "description": command.description,
                    "evidence": command.evidence,
                },
            ),
        )

    runtime_settings = settings or RuntimeSettings()
    runtime_state = build_runtime_state(runtime_settings)
    runtime_logger = configure_structured_logging(runtime_settings.log_level)
    repo = repository
    unit_of_work = LocalSqliteUnitOfWork(repo)
    domain_events = DomainEventCollector()
    audit = audit_logger
    gateway = ecosystem or MockEcosystemGateway()

    app = FastAPI(
        title="Generated UPI Dispute Resolution Application Legacy Injection Harness",
        version="0.39.1",
        description=BOUNDARY_NOTICE,
    )
    app.state.database_path = runtime_settings.sqlite_path
    app.state.runtime = runtime_state
    app.state.runtime_logger = runtime_logger
    app.state.compatibility_mode = "explicit_legacy_dependency_injection_harness"

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": exc.detail,
                    "path": request.url.path,
                    "boundary_notice": BOUNDARY_NOTICE,
                }
            },
        )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.as_error_payload(
                path=request.url.path,
                boundary_notice=BOUNDARY_NOTICE,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        runtime_state.counters.validation_failures += 1
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": jsonable_encoder(exc.errors()),
                    "path": request.url.path,
                    "boundary_notice": BOUNDARY_NOTICE,
                }
            },
        )

    async def get_repo() -> Any:
        return repo

    async def get_audit() -> Any:
        return audit

    async def get_gateway() -> Any:
        return gateway

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app_id": "upi_dispute_resolution",
            "boundary": "local_app_with_mock_external_ecosystem",
            "runtime_hardening": runtime_state.report.as_dict(),
            "compatibility_mode": app.state.compatibility_mode,
        }

    @app.get("/runtime/health")
    async def runtime_health() -> dict[str, object]:
        return {
            "status": runtime_state.report.status,
            "runtime_hardening": runtime_state.report.as_dict(),
            "compatibility_mode": app.state.compatibility_mode,
        }

    @app.get("/runtime/metrics")
    async def runtime_metrics() -> dict[str, object]:
        return {
            "status": "available",
            "metrics": runtime_state.counters.as_dict(),
            "observability_scope": "local_structured_runtime_counters_only",
            "live_provider_calls_allowed": False,
            "compatibility_mode": app.state.compatibility_mode,
        }

    @app.post(
        "/disputes",
        response_model=DisputeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_dispute(
        response: Response,
        payload: dict[str, Any] = Body(...),
        current_repo: Any = Depends(get_repo),
        current_audit: Any = Depends(get_audit),
    ) -> DisputeResponse:
        try:
            validated_payload = DisputeCreate.model_validate(payload)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        command = SubmitDisputeCommand.from_payload(validated_payload)
        try:
            assert_no_obvious_real_sensitive_values(command.description)
        except ValueError as exc:
            raise ApplicationError(
                AppErrorCode.VALIDATION_BOUNDARY,
                str(exc),
                http_status=422,
            ) from exc

        record = build_dispute_record(command)
        fingerprint = payload_fingerprint(command)
        business_fingerprint = business_duplicate_fingerprint(command)
        try:
            current_repo.add(
                record,
                request_fingerprint=fingerprint,
                business_fingerprint=business_fingerprint,
            )
            unit_of_work.commit()
        except DuplicateClientRequestError as exc:
            stored_fingerprint = current_repo.get_request_fingerprint(command.client_request_id)
            if stored_fingerprint == fingerprint:
                existing = current_repo.get_by_client_request_id(command.client_request_id)
                runtime_state.counters.idempotency_replays += 1
                response.status_code = status.HTTP_200_OK
                log_runtime_event(
                    runtime_logger,
                    event_type="idempotency_replay",
                    details={
                        "dispute_id": existing.dispute_id,
                        "client_request_id": existing.client_request_id,
                    },
                )
                return DisputeResponse(
                    dispute=existing,
                    next_actions=next_actions_for(existing),
                    boundary_notice=BOUNDARY_NOTICE,
                )
            raise ApplicationError(
                AppErrorCode.PAYLOAD_CONFLICT,
                "client_request_id already exists with a different payload",
                http_status=409,
            ) from exc
        except DuplicateBusinessSubmissionError as exc:
            raise ApplicationError(
                AppErrorCode.PAYLOAD_CONFLICT,
                "duplicate business dispute submission already exists",
                http_status=409,
            ) from exc

        runtime_state.counters.disputes_created += 1
        domain_events.record(dispute_created_event(record))
        emitted_events = [event.as_dict() for event in domain_events.drain()]
        current_audit.record(
            event_type="dispute_created",
            actor="api",
            dispute_id=record.dispute_id,
            details={
                "dispute_type": record.dispute_type.value,
                "status": record.status.value,
                "domain_events": emitted_events,
            },
        )
        log_runtime_event(
            runtime_logger,
            event_type="dispute_created",
            details={"dispute_id": record.dispute_id, "status": record.status.value},
        )
        return DisputeResponse(
            dispute=record,
            next_actions=next_actions_for(record),
            boundary_notice=BOUNDARY_NOTICE,
        )

    @app.get("/disputes", response_model=list[DisputeRecord])
    async def list_disputes(
        current_repo: Any = Depends(get_repo),
    ) -> list[DisputeRecord]:
        ListDisputesQuery()
        return cast(list[DisputeRecord], current_repo.list_all())

    @app.get("/disputes/{dispute_id}", response_model=DisputeResponse)
    async def get_dispute(
        dispute_id: str,
        current_repo: Any = Depends(get_repo),
    ) -> DisputeResponse:
        query = GetDisputeQuery(dispute_id=dispute_id)
        try:
            record = current_repo.get(query.dispute_id)
        except DisputeNotFoundError as exc:
            raise exc
        return DisputeResponse(
            dispute=record,
            next_actions=next_actions_for(record),
            boundary_notice=BOUNDARY_NOTICE,
        )

    @app.post(
        "/disputes/{dispute_id}/actions/mock-ecosystem-check",
        response_model=EcosystemCheckResult,
    )
    async def run_mock_ecosystem_check(
        dispute_id: str,
        current_repo: Any = Depends(get_repo),
        current_audit: Any = Depends(get_audit),
        current_gateway: Any = Depends(get_gateway),
    ) -> EcosystemCheckResult:
        command = RunMockEcosystemCheckCommand(dispute_id=dispute_id)
        try:
            record = current_repo.get(command.dispute_id)
        except DisputeNotFoundError as exc:
            raise exc

        decision, reason, sources = current_gateway.decide(record)
        new_status = status_from_ecosystem_decision(decision)
        updated = current_repo.update_status(
            dispute_id=command.dispute_id,
            status=new_status,
            updated_at_utc=utc_now_iso(),
            note=reason,
        )
        unit_of_work.commit()
        domain_events.record(
            mock_ecosystem_checked_event(
                updated,
                decision=decision.value,
                sources=sources,
            )
        )
        emitted_events = [event.as_dict() for event in domain_events.drain()]
        current_audit.record(
            event_type="mock_ecosystem_check_completed",
            actor="mock_ecosystem",
            dispute_id=command.dispute_id,
            details={
                "decision": decision.value,
                "new_status": updated.status.value,
                "sources": sources,
                "domain_events": emitted_events,
            },
        )
        runtime_state.counters.mock_ecosystem_checks += 1
        log_runtime_event(
            runtime_logger,
            event_type="mock_ecosystem_check_completed",
            details={"dispute_id": dispute_id, "decision": decision.value},
        )
        return EcosystemCheckResult(
            dispute_id=dispute_id,
            decision=decision,
            new_status=updated.status,
            reason=reason,
            mock_sources_checked=sources,
        )

    return app


def _supports_legacy_dependency_injection(
    repository: Any | None,
    audit_logger: Any | None,
) -> bool:
    if repository is None or audit_logger is None:
        return False
    repository_methods = (
        "add",
        "get",
        "get_by_client_request_id",
        "get_request_fingerprint",
        "list_all",
        "update_status",
    )
    if any(not hasattr(repository, method) for method in repository_methods):
        return False
    return hasattr(audit_logger, "record")


def create_app(
    *,
    database_path: Path | None = None,
    repository: Any | None = None,
    audit_logger: Any | None = None,
    ecosystem: Any | None = None,
    settings: Any | None = None,
    use_legacy_dependency_injection: bool = False,
    **_: Any,
) -> FastAPI:
    """Legacy import facade that always returns the hardened generated API by default."""
    resolved_database_path = database_path
    if resolved_database_path is None and settings is not None:
        settings.validate()
        resolved_database_path = settings.sqlite_path
    if (
        not use_legacy_dependency_injection
        and database_path is None
        and _supports_legacy_dependency_injection(repository, audit_logger)
    ):
        return _legacy_injection_app(
            repository=repository,
            audit_logger=audit_logger,
            ecosystem=ecosystem,
            settings=settings,
        )
    if not use_legacy_dependency_injection:
        return _hardened_api_app(database_path=resolved_database_path)
    if repository is None or audit_logger is None:
        raise ValueError("legacy injection harness requires repository and audit_logger together")
    return _legacy_injection_app(
        repository=repository,
        audit_logger=audit_logger,
        ecosystem=ecosystem,
        settings=settings,
    )


app = _hardened_api_app()
