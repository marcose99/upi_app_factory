from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class RuntimeConfigurationError(ValueError):
    pass


def _read_bool(raw: str, *, name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeConfigurationError(f"{name} must be true or false")


@dataclass(frozen=True)
class RuntimeSettings:
    app_env: str = "local"
    data_dir: Path = Path("var/local_runtime")
    sqlite_path: Path = Path("var/local_runtime/disputes.sqlite3")
    audit_log_path: Path = Path("var/local_runtime/audit_events.jsonl")
    log_level: str = "INFO"
    external_ecosystem_mode: str = "mock"
    enable_live_provider_calls: bool = False
    allow_real_secrets: bool = False
    idempotency_retention_hours: int = 24

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        source = env if env is not None else os.environ
        return cls(
            app_env=source.get("UPI_DISPUTE_APP_ENV", "local"),
            data_dir=Path(source.get("UPI_DISPUTE_DATA_DIR", "var/local_runtime")),
            sqlite_path=Path(source.get("UPI_DISPUTE_SQLITE_PATH", "var/local_runtime/disputes.sqlite3")),
            audit_log_path=Path(
                source.get("UPI_DISPUTE_AUDIT_LOG_PATH", "var/local_runtime/audit_events.jsonl")
            ),
            log_level=source.get("UPI_DISPUTE_LOG_LEVEL", "INFO"),
            external_ecosystem_mode=source.get("UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE", "mock"),
            enable_live_provider_calls=_read_bool(
                source.get("UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS", "false"),
                name="UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS",
            ),
            allow_real_secrets=_read_bool(
                source.get("UPI_DISPUTE_ALLOW_REAL_SECRETS", "false"),
                name="UPI_DISPUTE_ALLOW_REAL_SECRETS",
            ),
            idempotency_retention_hours=int(
                source.get("UPI_DISPUTE_IDEMPOTENCY_RETENTION_HOURS", "24")
            ),
        )

    def validate(self) -> None:
        if self.app_env not in {"local", "test"}:
            raise RuntimeConfigurationError("UPI_DISPUTE_APP_ENV must be local or test")
        if self.external_ecosystem_mode != "mock":
            raise RuntimeConfigurationError(
                "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE must remain mock"
            )
        if self.enable_live_provider_calls:
            raise RuntimeConfigurationError("live provider calls are not allowed")
        if self.allow_real_secrets:
            raise RuntimeConfigurationError("real secrets are not allowed")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise RuntimeConfigurationError("UPI_DISPUTE_LOG_LEVEL is not supported")
        if self.idempotency_retention_hours < 1 or self.idempotency_retention_hours > 168:
            raise RuntimeConfigurationError(
                "UPI_DISPUTE_IDEMPOTENCY_RETENTION_HOURS must be between 1 and 168"
            )
        self._validate_persistence_path(self.sqlite_path, setting_name="UPI_DISPUTE_SQLITE_PATH")
        self._validate_persistence_path(
            self.audit_log_path,
            setting_name="UPI_DISPUTE_AUDIT_LOG_PATH",
        )

    def _validate_persistence_path(self, path: Path, *, setting_name: str) -> None:
        if str(path) == ":memory:":
            return
        if ".." in path.parts:
            raise RuntimeConfigurationError(f"{setting_name} must not traverse directories")
        if path.is_absolute():
            if not path.is_relative_to(self.data_dir.resolve()):
                raise RuntimeConfigurationError(f"{setting_name} must stay within UPI_DISPUTE_DATA_DIR")
            return
        if not path.is_relative_to(self.data_dir):
            raise RuntimeConfigurationError(f"{setting_name} must stay within UPI_DISPUTE_DATA_DIR")
