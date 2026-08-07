from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from generated_application.app.infrastructure.persistence.migrations import apply_migrations


@dataclass
class RuntimeLifecycle:
    database_path: Path
    started: bool = False
    live: bool = False
    ready: bool = False
    draining: bool = False
    shutdown_complete: bool = False
    startup_checks: list[str] = field(default_factory=list)
    shutdown_checks: list[str] = field(default_factory=list)
    started_at_utc: str | None = None
    shutdown_at_utc: str | None = None
    restart_count: int = 0

    def startup(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            apply_migrations(connection)
            connection.commit()
        self.started = True
        self.live = True
        self.ready = True
        self.draining = False
        self.shutdown_complete = False
        self.restart_count += 1
        self.started_at_utc = datetime.now(timezone.utc).isoformat()
        self.startup_checks = ["sqlite_migrations_applied", "mock_dependencies_configured"]

    def dependency_health(self) -> dict[str, object]:
        checks: dict[str, object] = {
            "sqlite": {
                "status": "unknown",
                "path": str(self.database_path),
                "real_payment_calls_allowed": False,
            },
            "mock_upi_switch": {"status": "ok", "boundary": "MOCK_BOUNDARY"},
            "mock_core_banking": {"status": "ok", "boundary": "MOCK_BOUNDARY"},
        }
        try:
            with sqlite3.connect(self.database_path) as connection:
                result = connection.execute("pragma integrity_check").fetchone()[0]
            checks["sqlite"] = {
                "status": "ok" if result == "ok" else "degraded",
                "path": str(self.database_path),
                "integrity_check": str(result),
                "real_payment_calls_allowed": False,
            }
        except sqlite3.Error as exc:
            checks["sqlite"] = {
                "status": "degraded",
                "path": str(self.database_path),
                "error": exc.__class__.__name__,
                "real_payment_calls_allowed": False,
            }
        return checks

    def readiness(self) -> tuple[int, dict[str, object]]:
        dependencies = self.dependency_health()
        sqlite_status = dependencies["sqlite"]
        sqlite_ok = isinstance(sqlite_status, dict) and sqlite_status.get("status") == "ok"
        ready = self.started and self.live and self.ready and not self.draining and sqlite_ok
        status_code = 200 if ready else 503
        return status_code, {
            "status": "ready" if ready else "not_ready",
            "started": self.started,
            "live": self.live,
            "draining": self.draining,
            "dependencies": dependencies,
            "startup_checks": list(self.startup_checks),
        }

    def liveness(self) -> tuple[int, dict[str, object]]:
        live = self.started and self.live and not self.shutdown_complete
        return 200 if live else 503, {
            "status": "live" if live else "not_live",
            "started": self.started,
            "shutdown_complete": self.shutdown_complete,
        }

    def startup_status(self) -> tuple[int, dict[str, object]]:
        return 200 if self.started else 503, {
            "status": "started" if self.started else "starting",
            "started_at_utc": self.started_at_utc,
            "startup_checks": list(self.startup_checks),
        }

    def begin_drain(self) -> dict[str, object]:
        self.draining = True
        self.ready = False
        return {"status": "draining", "ready": self.ready, "live": self.live}

    def shutdown(self) -> None:
        self.ready = False
        self.draining = True
        self.live = False
        self.shutdown_complete = True
        self.shutdown_at_utc = datetime.now(timezone.utc).isoformat()
        self.shutdown_checks = ["readiness_disabled", "liveness_disabled"]

    def diagnostics(self) -> dict[str, object]:
        readiness_code, readiness = self.readiness()
        liveness_code, liveness = self.liveness()
        return {
            "schema_version": "upi_app_factory.generated.runtime_diagnostics.v1",
            "lifecycle": {
                "startup": self.startup_status()[1],
                "liveness": liveness,
                "readiness": readiness,
                "readiness_status_code": readiness_code,
                "liveness_status_code": liveness_code,
                "restart_count": self.restart_count,
                "shutdown_at_utc": self.shutdown_at_utc,
                "shutdown_checks": list(self.shutdown_checks),
            },
            "dependency_health": self.dependency_health(),
            "boundaries": {
                "live_payment_calls_allowed": False,
                "external_integrations": "mocked_or_simulated_only",
                "production_capacity_claimed": False,
            },
        }
