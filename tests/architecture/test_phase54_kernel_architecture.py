from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / "factory/application_engineering/local_platform_kernel.py"
PROHIBITED = {
    "sqlalchemy",
    "psycopg",
    "pymysql",
    "redis",
    "kafka",
    "pika",
    "elasticsearch",
    "kubernetes",
    "terraform",
    "docker",
}


def test_kernel_preserves_application_engineering_compatibility_path() -> None:
    assert KERNEL.is_file()
    assert "factory/application_engineering" in KERNEL.as_posix()


def test_kernel_uses_standard_library_sqlite_and_no_prohibited_stacks() -> None:
    source = KERNEL.read_text(encoding="utf-8")

    assert "import sqlite3" in source
    assert "CREATE TABLE IF NOT EXISTS kernel_migrations" in source
    lowered = source.lower()
    for dependency in PROHIBITED:
        assert dependency not in lowered


def test_kernel_keeps_local_governance_boundaries() -> None:
    source = KERNEL.read_text(encoding="utf-8")

    assert 'service_name: str = "upi_app_factory"' in source
    assert 'runtime_llm_calls_default: int = 0' in source
    assert 'real_payment_calls: str = "disabled"' in source
    assert "FictionalLocalAuthorizer" in source
