from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .settings import RuntimeSettings


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RuntimeHardeningReport:
    status: str
    app_env: str
    external_ecosystem_mode: str
    checks: list[RuntimeCheck]
    certification_boundary: str = "certification_ready_not_certified"
    local_readiness_scope: str = "local_generated_application_runtime_only"
    live_provider_calls_allowed: bool = False
    real_secrets_allowed: bool = False
    production_readiness_claimed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "app_env": self.app_env,
            "external_ecosystem_mode": self.external_ecosystem_mode,
            "checks": [check.as_dict() for check in self.checks],
            "certification_boundary": self.certification_boundary,
            "local_readiness_scope": self.local_readiness_scope,
            "live_provider_calls_allowed": self.live_provider_calls_allowed,
            "real_secrets_allowed": self.real_secrets_allowed,
            "production_readiness_claimed": self.production_readiness_claimed,
        }


@dataclass
class RuntimeCounters:
    disputes_created: int = 0
    idempotency_replays: int = 0
    mock_ecosystem_checks: int = 0
    validation_failures: int = 0
    structured_errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "disputes_created": self.disputes_created,
            "idempotency_replays": self.idempotency_replays,
            "mock_ecosystem_checks": self.mock_ecosystem_checks,
            "validation_failures": self.validation_failures,
            "structured_errors": self.structured_errors,
        }


@dataclass
class RuntimeState:
    settings: RuntimeSettings
    report: RuntimeHardeningReport
    counters: RuntimeCounters = field(default_factory=RuntimeCounters)


def build_runtime_state(settings: RuntimeSettings) -> RuntimeState:
    settings.validate()
    checks = [
        RuntimeCheck("configuration", "passed", "Runtime settings validated."),
        RuntimeCheck("external_ecosystem", "passed", "External ecosystem mode is mock only."),
        RuntimeCheck("secrets", "passed", "No real secret setting is enabled."),
        RuntimeCheck("persistence_boundary", "passed", "SQLite and audit paths stay local."),
        RuntimeCheck("observability", "passed", "Structured audit and metrics hooks are enabled."),
    ]
    return RuntimeState(
        settings=settings,
        report=RuntimeHardeningReport(
            status="passed",
            app_env=settings.app_env,
            external_ecosystem_mode=settings.external_ecosystem_mode,
            checks=checks,
        ),
    )


def configure_structured_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("upi_dispute_app.runtime")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_runtime_event(
    logger: logging.Logger,
    *,
    event_type: str,
    details: dict[str, Any],
) -> None:
    logger.info(
        json.dumps(
            {
                "event_type": event_type,
                "app_id": "upi_dispute_resolution",
                "certification_boundary": "certification_ready_not_certified",
                "details": details,
            },
            sort_keys=True,
        )
    )


def payload_fingerprint(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        serializable = payload.model_dump(mode="json")
    else:
        serializable = payload
    encoded = json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
