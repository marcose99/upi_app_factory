from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
APP_SOURCE = GENERATED_APP_ROOT / "app"
if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.settings import RuntimeSettings  # noqa: E402


def _make_settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        app_env="test",
        data_dir=tmp_path,
        sqlite_path=tmp_path / "disputes.sqlite3",
        audit_log_path=tmp_path / "audit_events.jsonl",
    )


def test_create_app_keeps_hardened_runtime_as_default_even_with_legacy_injection_args(
    tmp_path: Path,
) -> None:
    app = create_app(
        repository=object(),
        audit_logger=object(),
        settings=_make_settings(tmp_path),
    )

    assert getattr(app.state, "database_path") == tmp_path / "disputes.sqlite3"
    assert not hasattr(app.state, "compatibility_mode")


def test_create_app_allows_explicit_legacy_dependency_injection_opt_in(tmp_path: Path) -> None:
    app = create_app(
        repository=object(),
        audit_logger=object(),
        settings=_make_settings(tmp_path),
        use_legacy_dependency_injection=True,
    )

    assert getattr(app.state, "compatibility_mode") == "explicit_legacy_dependency_injection_harness"
