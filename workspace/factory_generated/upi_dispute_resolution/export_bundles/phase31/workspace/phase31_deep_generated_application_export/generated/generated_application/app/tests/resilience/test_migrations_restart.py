from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.domain.exceptions import MigrationDriftError
from generated_application.app.infrastructure.persistence.migrations import MIGRATIONS, apply_migrations
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork


def test_migrations_are_repeatable_and_checksummed(tmp_path: Path) -> None:
    database = tmp_path / "migrations.sqlite3"
    with SqliteUnitOfWork(database) as uow:
        uow.commit()
    with SqliteUnitOfWork(database) as uow:
        versions = uow.connection.execute("select version from schema_migrations order by version").fetchall()
        uow.commit()

    assert [row[0] for row in versions] == [migration.version for migration in MIGRATIONS]


def test_migration_checksum_drift_blocks_restart(tmp_path: Path) -> None:
    database = tmp_path / "drift.sqlite3"
    with sqlite3.connect(database) as connection:
        apply_migrations(connection)
        connection.execute("update schema_migrations set checksum = ? where version = 2", ("tampered",))
        connection.commit()

    with sqlite3.connect(database) as connection:
        with pytest.raises(MigrationDriftError):
            apply_migrations(connection)
